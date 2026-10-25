"""共用選單九種已觀測表形：精確資料綁定與代表性正常路徑抽驗。"""
import base64
import csv
import hashlib
from pathlib import Path
import shutil
import struct
import sys
import tempfile

from PIL import Image
from original_prefix_check import catalog, image, read
from passage_runtime_inputs import record, sha, write

PARENT="manual-reader-rows-20261025/inputs-r1"
MENUS={
 "326aacadb1a01c55f2e08f88cd3fc3ce209f7cfb0826f53439bd66558839a4dc":("weapon-hud-20261025/observe-r5/receipt.json","combat"),
 "72c4041e90650eaa2c0b46505cfc183082f23966891560a9b9dec4ad6e4fdfaa":("haste-battle-20261025/observe-inv-r1/receipt.json","exploration"),
 "cf58f5f75c722981e959125027e481a191483f9e49f397697e9ee4ccdc87322f":("haste-battle-20261025/observe-inv-r1/receipt.json","exploration"),
 "3477e4b72381abaf1055e6e99f06469c212ead02a9245d81e8aaedf663e405e9":("haste-battle-20261025/observe-r3/receipt.json","grimoire"),
 "b31ad9ff3c57500d9ed2680861285f6f750e60f24f92fb6cf42ae457ecf5f9c3":("combat-aim-route-20261024/observe-r1/receipt.json","aim"),
 "3c02c5279c288a2d6dae6d8f570a024c8ea8b44d788e661c82b5ba76695a7012":("combat-aim-route-20261024/observe-r1/receipt.json","aim"),
 "c5b214e0c009d9bf9bb1be3435f8b0c72be521577ac3912c57dfa55d39b0a5c2":("combat-rounds-20261024/observe-r3/receipt.json","combat"),
 "fc2face68b53809969febbc56fec8d8f3d8160b6ad62cc4f2115f401bca89c9b":("combat-rounds-20261024/observe-r1/receipt.json","combat"),
 "6e2f6b5cbb3b4899d98ba0d68198f3b420d693845aa76fcd2550e66f5eb7fc40":("victory-text-20261025/dock-observe-r1/receipt.json","choice"),
}
STATES={"inv":"battle-text-20261024/observe-gate-r1/final.state",
        "aim":"combat-spells-route-20261024/observe-r3/final.state",
        "port":"victory-text-20261025/post-observe-r7/final.state"}


def digest(value):return hashlib.sha256(value).hexdigest()


def derive(root):
    probe=root / "workplace/probe"
    parent=probe / PARENT
    cfg=read(parent / "inputs.json")
    en,zh=[catalog(parent / n) for n in ("en.tsv","zh-TW.tsv")]
    with (root / "text/shared-menu.zh-TW.tsv").open() as f:
        reader=csv.DictReader(f,delimiter="\t",quoting=csv.QUOTE_NONE)
        assert reader.fieldnames==["key","en","zh-TW"]
        rows=list(reader)
    assert all(set(r)=={"key","en","zh-TW"} and all(r.values()) for r in rows)
    assert len(rows)==8 and len({r["key"] for r in rows})==8
    for row in rows:
        k=row["key"]
        assert k not in en and k not in zh and 0<len(row["zh-TW"])<=len(row["en"])
        assert set(row["zh-TW"])<=read(parent / "glyphs-16.json")["glyphs"].keys()
        en[k],zh[k]=row["en"],row["zh-TW"]
    formal_en=catalog(root / "workplace/translation/en.tsv")
    formal_zh=catalog(root / "workplace/translation/zh-TW.tsv")
    for key,old in (("menu.shared.attack","ecl.301de93e8a2746a7933c"),("menu.shared.explain","ecl.a42f134d4d2368c38044")):
        assert en[key].upper()==formal_en[old] and zh[key]==formal_zh[old]
    data={}
    for sig,(source,kind) in MENUS.items():
        trace=read(probe / source)
        mi,m=next((i,m) for i,m in enumerate(trace["menus"]) if m["Signature"]==sig)
        assert sig not in cfg["Menus"]
        buttons=m["Buttons"]
        signature=[m["Count"],[[b[k] for k in ("Index","SHA256","RawX","RawY")] for b in buttons]]
        import json
        assert digest(json.dumps(signature,separators=(",",":")).encode())==sig
        raw=bytes.fromhex(m["RawHex"])
        fields=[]
        for b in buttons:
            value=bytes.fromhex(b["SourceHex"]).decode("ascii")
            assert digest(value.encode())==b["SHA256"]
            at=b["Index"]*32
            assert struct.unpack_from("<HH",raw,at)==(0x8e,0xceb)
            assert struct.unpack_from("<HH",raw,at+12)==(b["SourcePointer"]["Off"],b["SourcePointer"]["Seg"])
            assert struct.unpack_from("<HH",raw,at+16)==(b["RawY"],b["RawX"])
            keys=[k for k,v in en.items() if v==value and k in zh]
            assert keys and len({zh[k] for k in keys})==1,value
            key=min(keys)
            field=dict(Pane="menu",Group="footer",Key=key,Start=0,Length=len(value),SHA256=b["SHA256"],
                       FormatSHA256=b["SHA256"],Caller=dict(Seg=0xceb,Off=0x1be),
                       RawX=(b["RawX"]-8000)*2,RawY=(b["RawY"]-8000)*2+1,MenuSignature=sig)
            assert field["RawY"] in (179,189,191) and 0<=field["RawX"]<320
            fields.append(field)
        calls=[c for c in trace["calls"] if c.get("menu_index")==mi and c["caller"]==dict(Seg=0xceb,Off=0x1be)]
        assert calls and all(c["step"]<c["first_glyph"]<c["return_step"] for c in calls)
        cfg["Menus"][sig]=kind
        cfg["Fields"].extend(fields)
        data[sig]=dict(source=source,menu=m,fields=fields,actual_calls=calls)
    assert sum(len(d["fields"]) for d in data.values())==49
    return cfg,en,zh,data


def prepare(root,out):
    assert not (out / "evidence.json").exists()
    cfg,en,zh,data=derive(root)
    target=out / "inputs-r1"
    assert not target.exists()
    shutil.copytree(root / "workplace/probe" / PARENT,target)
    cfg["fine_windows"]=[]
    write(target / "inputs.json",cfg)
    for name,values in (("en.tsv",en),("zh-TW.tsv",zh)):
        (target / name).write_text("key\ttext\n"+"".join(k+"\t"+v+"\n" for k,v in sorted(values.items())))
    write(out / "bindings.json",data)
    provenance=read(target / "provenance.json")
    provenance["shared_menu_extension"]=dict(parent=PARENT,ui=record(root / "text/shared-menu.zh-TW.tsv"),
          bindings_sha256=sha(out / "bindings.json"),en_sha256=sha(target / "en.tsv"),zh_sha256=sha(target / "zh-TW.tsv"))
    write(target / "provenance.json",provenance)
    probe=root / "workplace/probe"
    for case,source in (("inv","haste-battle-20261025/observe-inv-r1"),("aim","combat-aim-route-20261024/observe-r1")):
        request=read(probe / source / "receipt.json")["request"]
        assert request["state_sha256"]==sha(probe / STATES[case])
        write(out / (case+"-request.json"),request)
    write(out / "port-request-r2.json",dict(state_sha256=sha(probe / STATES["port"]),start_steps=5186000000,
          actions=[dict(at=5187000000,end=5266000000,kind="text",key="e",label="explain-to-sailors")]))
    print("nine exact menu signatures, 49 bindings, eight context keys, no program or glyph changes")


def samples(root,out):
    assert not (out / "evidence.json").exists()
    windows=[]
    summary={}
    for case in STATES:
        suffix="-r2" if case=="port" else ""
        a,b=[read(out / (case+"-"+mode+suffix) / "receipt.json") for mode in ("observe","control")]
        assert a["checkpoints"]==b["checkpoints"]
        assert sha(out / (case+"-observe"+suffix) / "final.state")==sha(out / (case+"-control"+suffix) / "final.state")
        calls=[c for c in a["calls"] if c["caller"]==dict(Seg=0xceb,Off=0x1be) and a["menus"][c["menu_index"]]["Signature"] in MENUS]
        assert calls,case
        windows.extend([c[k]-2000,c[k]+4000] for c in calls for k in ("step","first_glyph","return_step"))
        summary[case]=dict(menu_calls=len(calls),native_checkpoints=len(a["checkpoints"]))
    cfg=read(out / "inputs-r1/inputs.json");cfg["fine_windows"]=windows
    write(out / "inputs-r1/inputs.json",cfg)
    write(out / "samples.json",summary)
    print(summary)


def samples_entry(root,out):
    assert not (out / "evidence.json").exists()
    a,b=[read(out / ("port-entry-"+mode) / "receipt.json") for mode in ("observe","control")]
    assert a["checkpoints"]==b["checkpoints"]
    assert sha(out / "port-entry-observe/final.state")==sha(out / "port-entry-control/final.state")
    calls=[c for c in a["calls"] if c["caller"]==dict(Seg=0xceb,Off=0x1be) and a["menus"][c["menu_index"]]["Signature"] in MENUS]
    assert {c["format"]["text"] for c in calls}=={"Attack","Explain"} and len(calls)==3
    target=out / "inputs-r2"
    assert not target.exists()
    shutil.copytree(out / "inputs-r1",target)
    cfg=read(target / "inputs.json")
    cfg["fine_windows"].extend([c[k]-2000,c[k]+4000] for c in calls for k in ("step","first_glyph","return_step"))
    write(target / "inputs.json",cfg)
    print("continuous port entry",len(calls),"sources, both buttons")


def check(root,out):
    assert not (out / "evidence.json").exists()
    cfg,en,zh,data=derive(root)
    current=read(out / "inputs-r1/inputs.json")
    assert {k:v for k,v in cfg.items() if k!="fine_windows"}=={k:v for k,v in current.items() if k!="fine_windows"}
    final=read(out / "inputs-r2/inputs.json")
    assert {k:v for k,v in final.items() if k!="fine_windows"}=={k:v for k,v in current.items() if k!="fine_windows"}
    for p in (out / "inputs-r1").iterdir():
        if p.is_file() and p.name!="inputs.json":assert sha(p)==sha(out / "inputs-r2" / p.name),p.name
    assert sha(root / "workplace/probe/manual-reader-rows-20261025/programs-r1/ui-list-live")=="a5ca8ede85042db939ada5780c4a84910dddf3e0acad96fd6ec203dae565f1f7"
    assert data==read(out / "bindings.json")
    parent=root / "workplace/probe" / PARENT
    for p in parent.iterdir():
        if p.is_file() and p.name not in ("inputs.json","en.tsv","zh-TW.tsv","provenance.json"):
            assert sha(p)==sha(out / "inputs-r1" / p.name),p.name
    assert catalog(out / "inputs-r1/en.tsv")==en and catalog(out / "inputs-r1/zh-TW.tsv")==zh
    glyphs=read(parent / "glyphs-16.json")
    masks={k:Image.frombytes("L",(16,20),base64.b64decode(v)) for k,v in glyphs["glyphs"].items()}
    summaries={}
    for case in ("inv","aim","port-entry"):
        suffix=""
        case_inputs=out / ("inputs-r2" if case=="port-entry" else "inputs-r1")
        state=out / "port-prefix-3/final.state" if case=="port-entry" else root / "workplace/probe" / STATES[case]
        native=read(out / (case+"-observe"+suffix) / "receipt.json")
        control=read(out / (case+"-control"+suffix) / "receipt.json")
        a,b=[read(out / (case+"-"+lang+"-r2") / "receipt.json") for lang in ("en","zh")]
        assert native["checkpoints"]==control["checkpoints"]
        fields=("regs","ram_sha256","indexed_sha256","palette","keys_consumed","file_writes","step","label")
        for run in (a,b):
            assert not run["unimplemented"] and run["initial_state_sha256"]==sha(state)
            assert run["list_inputs_sha256"]==sha(case_inputs / "inputs.json")
            assert len(run["checkpoints"])==len(control["checkpoints"])
            for cp,orig in zip(run["checkpoints"],control["checkpoints"]):
                assert all(cp[k]==orig[k] for k in fields),cp["label"]
                assert not cp["file_writes"] and not orig["unimplemented"]
        calls=[c for c in native["calls"] if c["caller"]==dict(Seg=0xceb,Off=0x1be) and native["menus"][c["menu_index"]]["Signature"] in MENUS]
        events=[e for e in b["list_events"] if e["Kind"]=="field-before-glyph" and e["detail"].get("menu_signature") in MENUS]
        assert len(calls)==len(events)
        actual_keys=set()
        for call,event in zip(calls,events):
            sig=native["menus"][call["menu_index"]]["Signature"]
            value=call["format"]["text"]
            f=next(f for f in data[sig]["fields"] if en[f["Key"]]==value)
            w=event["detail"]["word"]
            assert event["Step"]==call["step"]<event["first_glyph"]==call["first_glyph"]<call["return_step"]
            assert (w["Key"],w["X"],w["Y"],w["Width"])==(f["Key"],f["RawX"],f["RawY"],len(value)*8)
            actual_keys.add(w["Key"])
        assert [f["step"] for f in a["frames"]]==[f["step"] for f in b["frames"]]
        assert len(b["frames"])==len(b["list_frames"])
        cps={c["step"]:c for c in control["checkpoints"]}
        visible={k:0 for k in actual_keys};held=paragraphs=0;last=None
        for x,y,meta in zip(a["frames"],b["frames"],b["list_frames"]):
            english=image(out / (case+"-en-r2") / x["File"])
            chinese=image(out / (case+"-zh-r2") / y["File"])
            for f,im in ((x,english),(y,chinese)):
                assert digest(im.convert("RGBA").tobytes())==f["SHA256"]
            if x["step"] in cps:
                expected=image(out / (case+"-control"+suffix) / (cps[x["step"]]["label"]+".png")).resize((640,400),Image.Resampling.NEAREST)
                assert english.tobytes()==expected.tobytes()
            if y["held"]:
                assert last is not None and y["SHA256"]==last["SHA256"],(case,y["step"],"hold")
                held+=1
            else:
                expected=english.copy()
                for w in meta["words"] or []:
                    xx,yy,width,height=w["X"]*2,w["Y"]*2,w["Width"]*2,w.get("Height",8)*2
                    bg,fg=[tuple(meta["palette"][w[n]]) for n in ("Background","Foreground")]
                    expected.paste(bg,(xx,yy,xx+width,yy+height))
                    text=zh[w["Key"]]
                    if "Number" in w:text=text.replace("%d",str(w["Number"]))
                    assert len(text)*16<=width
                    for i,ch in enumerate(text):expected.paste(fg,(xx+i*16,yy,xx+(i+1)*16,yy+20),masks[ch])
                    if w.get("Button") and w["Key"] in visible:visible[w["Key"]]+=1
                page=meta["paragraph"]
                if page:
                    assert not page.get("Prefix") and case.startswith("port")
                    colors=[]
                    components=page.get("Components") or [page["Key"]]
                    for key,color in zip(components,page.get("ComponentColors") or [page["Foreground"]]*len(components)):
                        colors.extend([color]*len(zh[key]))
                    assert sum(map(len,page["Lines"]))==len(colors)
                    expected.paste(tuple(meta["palette"][page["Background"]]),(16,272,624,368))
                    at=0
                    for row,line in enumerate(page["Lines"]):
                        for col,ch in enumerate(line):
                            fg=tuple(meta["palette"][colors[at]]);xx,yy=16+col*16,272+row*20
                            expected.paste(fg,(xx,yy,xx+16,yy+20),masks[ch]);at+=1
                    paragraphs+=1
                    assert not any(w.get("Button") and w["Key"].startswith("menu.shared.") for w in meta["words"] or [])
                assert chinese.tobytes()==expected.tobytes(),(case,y["step"],"composition")
            last=y
        if case=="inv":assert all(visible[k]>0 for k in actual_keys)
        if case=="aim":assert all(visible[k]>0 for k in actual_keys)
        if case.startswith("port"):
            assert paragraphs>0 and all(visible[k]>0 for k in actual_keys)
        summaries[case]=dict(gpu_pairs=len(b["frames"]),native_checkpoints=len(control["checkpoints"]),
                             actual_button_sources=len(calls),visible_buttons=visible,held=held,paragraph_samples=paragraphs)
    write(out / "check.json",dict(menu_signatures=9,bindings=49,new_context_keys=8,source=len(en),translated=len(zh),
          glyphs_unchanged=True,program_unchanged=True,original_state_equal=True,cases=summaries,
          limits="三條代表路徑；其餘戰鬥表形只核實際原版來源。快照未重印的既有介面及港口入場敘事不列中文通過。"))
    print(read(out / "check.json"))


def rebuild(root,out):
    assert not (out / "evidence.json").exists()
    with tempfile.TemporaryDirectory(prefix="rebuild-",dir=out) as directory:
        fresh=Path(directory)
        prepare(root,fresh)
        cfg=read(fresh / "inputs-r1/inputs.json")
        windows=[]
        for case in STATES:
            suffix="-r2" if case=="port" else ""
            trace=read(out / (case+"-observe"+suffix) / "receipt.json")
            calls=[c for c in trace["calls"] if c["caller"]==dict(Seg=0xceb,Off=0x1be) and trace["menus"][c["menu_index"]]["Signature"] in MENUS]
            windows.extend([c[k]-2000,c[k]+4000] for c in calls for k in ("step","first_glyph","return_step"))
        cfg["fine_windows"]=windows
        write(fresh / "inputs-r1/inputs.json",cfg)
        for p in (out / "inputs-r1").iterdir():
            if p.is_file():assert sha(fresh / "inputs-r1" / p.name)==sha(p),p.name
        assert sha(fresh / "bindings.json")==sha(out / "bindings.json")
        shutil.copytree(fresh / "inputs-r1",fresh / "inputs-r2")
        trace=read(out / "port-entry-observe/receipt.json")
        calls=[c for c in trace["calls"] if c["caller"]==dict(Seg=0xceb,Off=0x1be) and trace["menus"][c["menu_index"]]["Signature"] in MENUS]
        cfg["fine_windows"].extend([c[k]-2000,c[k]+4000] for c in calls for k in ("step","first_glyph","return_step"))
        write(fresh / "inputs-r2/inputs.json",cfg)
        for p in (out / "inputs-r2").iterdir():
            if p.is_file():assert sha(fresh / "inputs-r2" / p.name)==sha(p),p.name
    write(out / "rebuild.json",dict(input_files_per_profile=18,profiles=2,bindings_equal=True,all_inputs_equal=True))
    print("two profiles, 18 files each rebuilt identical")


def seal(root,out):
    assert not (out / "evidence.json").exists()
    assert read(out / "check.json")["original_state_equal"] and read(out / "prefix-check.json")["state_equal"]
    assert read(out / "rebuild.json")["all_inputs_equal"]
    names=("shared_menu_inputs.py","original_prefix_check.py","passage_runtime_inputs.py","passage_chain_inputs.py",
           "original_prefix_inputs.py","text_catalog.py","research_storage.py")
    snapshots=out / "tool-snapshots";snapshots.mkdir()
    for n in names:shutil.copyfile(root / "tools" / n,snapshots / n)
    paths={root / "workplace/probe" / name for name,kind in MENUS.values()}
    paths.update(root / "workplace/probe" / name for name in STATES.values())
    paths.update(p for p in (root / "workplace/probe" / PARENT).iterdir() if p.is_file())
    paths.update(root / n for n in ("text/shared-menu.zh-TW.tsv","workplace/translation/en.tsv","workplace/translation/zh-TW.tsv",
        "workplace/input/dos/drkqueen/DQK.EXE","workplace/input/dos/drkqueen/DISK3/ECL.GLB",
        "workplace/probe/manual-gameplay-20261023/appendix-r1/core-review/operation-review.zh-TW.tsv",
        "workplace/probe/manual-gameplay-20261023/appendix-r1/core-review/source-review.json",
        "workplace/probe/manual-reader-rows-20261025/programs-r1/ui-list-live",
        "workplace/probe/combat-aim-route-20261024/programs-r3/ui-context-probe",
        "workplace/probe/victory-text-20261025/post-observe-r6/final.state",
        "workplace/probe/victory-text-20261025/post-observe-r7/receipt.json"))
    write(out / "evidence.json",dict(state="SEALED",draft=True,summary=read(out / "check.json"),
          artifacts={str(p.relative_to(out)):record(p) for p in sorted(out.rglob("*")) if p.is_file()},
          sources={str(p.relative_to(root)):record(p) for p in sorted(paths)},tools={n:record(snapshots / n) for n in names}))
    audit(root,out)


def audit(root,out):
    index=read(out / "evidence.json");assert index["state"]=="SEALED"
    for path,expected in index["artifacts"].items():assert record(out / path)==expected,path
    for path,expected in index["sources"].items():assert record(root / path)==expected,path
    for n,expected in index["tools"].items():assert record(out / "tool-snapshots" / n)==expected,n
    print("sealed audit",{k:len(index[k]) for k in ("artifacts","sources","tools")})


if __name__ == "__main__":
    mode,project,directory=sys.argv[1:]
    assert mode in ("prepare","samples","samples_entry","check","rebuild","seal","audit")
    globals()[mode](Path(project),Path(directory))
