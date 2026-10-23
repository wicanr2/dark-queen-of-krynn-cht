"""從獨立 MZ 觀測建立冷讀提示模型，提供 cold_load.py 逐幀比對。"""
import base64
import csv
import hashlib
import json
from pathlib import Path
import sys


def sha(data):return hashlib.sha256(data).hexdigest()
def read(path):return json.loads(path.read_text())
def catalog(path):return dict(line.split("\t",1) for line in path.read_text().splitlines()[1:])
def snapshot(words):return sorted(words.values(),key=lambda w:(w["Y"],w["X"]))
def intersects(w,r):return w["X"]<r[0]+r[2] and w["X"]+w["Width"]>r[0] and w["Y"]<r[1]+r[3] and w["Y"]+8>r[1]
def native(v):return v if v<400 else (v-8000)*2


def model(probe,a,b):
    assert a["cold_ui"]["input_root"]==b["cold_ui"]["input_root"]
    inputs=Path(b["cold_ui"]["input_root"])
    assert inputs.resolve().is_relative_to(probe.resolve())
    for run in (a,b):
        for name,digest in run["cold_ui"]["files"].items():
            assert Path(name).name==name and sha((inputs/name).read_bytes())==digest
    en,zh=catalog(inputs/"en.tsv"),catalog(inputs/"zh-TW.tsv")
    config,origin=read(inputs/"bindings.json"),read(inputs/"provenance.json")
    formal=Path("/catalogs")
    main_en,main_zh=catalog(formal/"en.tsv"),catalog(formal/"zh-TW.tsv")
    review={r["key"]:r for r in csv.DictReader((formal/"load-ui-review.tsv").open(),delimiter="\t")}
    for name,digest in origin["source_files"].items():assert sha((formal/name).read_bytes())==digest
    for key,source in origin["origins"].items():
        if "formal_key" in source:
            root=source["formal_key"]
            assert (source["en"],source["zh"])==(main_en[root],main_zh[root])
            assert en[key]==(main_en[root].rstrip(" ") if source["rule"]=="rstrip-space" else main_en[root])
            assert zh[key]==main_zh[root]
        else:
            row=review[source["review_key"]]
            assert row==source["review"] and (en[key],zh[key])==(row["en"],row["zh-TW"])
    trace_path=Path(origin["observed_path"])
    assert trace_path.resolve().is_relative_to(probe.resolve()) and sha(trace_path.read_bytes())==origin["observed_sha256"]
    trace=read(trace_path)
    assert trace["cold_boot"] and not trace["snapshot_loaded"] and not trace["pending_boot_menus"]
    assert len(en)==len(zh)==len(config["Bindings"])==6
    calls_by_step={c["step"]:c for c in trace["calls"]}
    evidence={row["key"]:row for row in origin["glyph_evidence"]}
    for binding in config["Bindings"]:
        key=binding["Key"]
        call=calls_by_step[evidence[key]["call_step"]]
        assert call["glyph_calls"]==evidence[key]["glyph_calls"]
        assert binding["SourceSHA256"]==sha(en[key].encode()) and binding["Width"]==len(en[key])*8
        assert binding["X"]==native(binding["RawX"]) and binding["Y"]==native(binding["RawY"])==189
        assert len(zh[key])*8<=binding["Width"]
        assert binding["Caller"]==call["caller"] and [binding["RawY"],binding["RawX"]]==call["stack"][2:4]
        assert binding["Background"]==(call["stack"][4]>>4)&15
        assert [binding["Y"],binding["X"]]==call["glyph_calls"][0]["stack"][2:4]
        assert binding["FormatSHA256"]==sha(call["format"]["text"].encode())
        if binding["Button"]:
            assert binding["MenuSignature"]==trace["menus"][call["menu_index"]]["Signature"]
            assert config["Menus"][binding["MenuSignature"]]==binding["Group"]
        else:
            assert binding["Color"]==call["stack"][4]
            wrapper=trace["wrappers"][call["wrapper_index"]]
            assert binding["UpperCaller"]==wrapper["caller"]
            assert binding["UpperFormatSHA256"]==sha(wrapper["format"]["text"].encode())
    glyphs=read(inputs/"glyphs-16.json")
    assert glyphs["size"]==16 and glyphs["height"]==20
    alpha={key:base64.b64decode(value) for key,value in glyphs["glyphs"].items()}
    assert all(len(v)==320 and not any(v[256:]) for v in alpha.values())
    # 比較來源可為另一條正常輸入路徑；每條路徑要有自己的 MZ 觀測收據。
    if origin.get("validation_trace"):
        trace_path=Path(origin["validation_trace"]["path"])
        assert trace_path.resolve().is_relative_to(probe.resolve())
        assert sha(trace_path.read_bytes())==origin["validation_trace"]["sha256"]
        trace=read(trace_path)
        assert trace["cold_boot"] and not trace["snapshot_loaded"]
    schedule=[]
    for event in trace["boot_menu_events"]:schedule.append((event["step"],"menu",event))
    for event in trace["fill_events"] or []:
        schedule.append((event["converted_step"],"clear",event))
        schedule.append((event["return_instruction_step"],"clear-return",event))
    for call in trace["calls"]:
        source=call["vararg_1_candidate"]["text"] if call["format"]["text"]=="%s" else call["format"]["text"]
        matches=[]
        for binding in config["Bindings"]:
            if binding["Caller"]!=call["caller"] or [binding["RawY"],binding["RawX"]]!=call["stack"][2:4]:continue
            if binding["SourceSHA256"]!=sha(source.encode()) or binding["FormatSHA256"]!=sha(call["format"]["text"].encode()):continue
            if "Color" in binding and binding["Color"]!=call["stack"][4]:continue
            if binding["Button"]:
                assert call["menu_index"]>=0
                if trace["menus"][call["menu_index"]]["Signature"]!=binding["MenuSignature"]:continue
            else:
                wrapper=trace["wrappers"][call["wrapper_index"]]
                if wrapper["caller"]!=binding["UpperCaller"] or sha(wrapper["format"]["text"].encode())!=binding["UpperFormatSHA256"]:continue
                assert wrapper["step"]<call["step"]<call["return_step"]<wrapper["return_step"]
            matches.append(binding)
        assert len(matches)<=1
        if matches:schedule.append((call["step"],"word",(call,matches[0])))
    words={};affected=set();events=[];timeline=[]
    def erase(rect):
        removed=[p for p,w in words.items() if intersects(w,rect)]
        for p in removed:del words[p]
        return bool(removed)
    for step,kind,data in sorted(schedule,key=lambda e:e[0]):
        event=None
        if kind=="menu":
            menu=data["menu"];pane=config["Menus"].get(menu["Signature"],"") if data["valid"] else ""
            footer=data["valid"] and all(btn["RawY"]==8094 for btn in menu["Buttons"])
            for p,w in list(words.items()):
                if not footer or (w.get("Button") and not pane) or w["Group"]=="loading" or (pane and w["Group"]!=pane):del words[p]
            event=dict(step=step,kind="menu-entry",detail=dict(menu=menu,valid=data["valid"],pane=pane),words=snapshot(words))
        elif kind=="clear":
            rect=data["native_rect"]
            if erase(rect):
                affected.add(data["step"])
                event=dict(step=step,kind="native-clear",detail=dict(entry_step=data["step"],rect=rect),words=snapshot(words))
        elif kind=="clear-return":
            if data["step"] in affected:
                affected.remove(data["step"])
                event=dict(step=step,kind="native-clear-return",detail=dict(entry_step=data["step"]),words=snapshot(words))
        else:
            call,binding=data
            assert call["step"]<call["first_glyph"]<call["return_step"]
            word=dict(X=binding["X"],Y=binding["Y"],Width=binding["Width"],Key=binding["Key"],Group=binding["Group"],Foreground=call["stack"][4]&15,Background=binding["Background"])
            if binding["Button"]:word["Button"]=True
            erase([word["X"],word["Y"],word["Width"],8]);words[word["X"],word["Y"]]=word
            event=dict(step=step,kind="word-before-glyph",detail=dict(key=binding["Key"],source_sha256=binding["SourceSHA256"],format_sha256=binding["FormatSHA256"],caller=call["caller"],word=word),words=snapshot(words),first_glyph=call["first_glyph"])
        if event:
            if not event["words"]:event["words"]=None
            events.append(event);timeline.append((step,event["words"] or [],bool(affected),len(events)))
    assert not words and not affected
    for run in (a,b):assert run["cold_ui"]["events"]==events
    for run in (a,b):
        frames={f["step"]:f for f in run["cold_frames"]}
        for cp in run["cold_checkpoints"]:
            previous=[e for e in trace["boot_menu_events"] if e["step"]<cp["step"] and e["valid"]]
            if not previous:continue
            pane=config["Menus"].get(previous[-1]["menu"]["Signature"])
            if pane:
                expected={binding["Key"] for binding in config["Bindings"] if binding["Group"]==pane}
                actual={w["Key"] for w in frames[cp["step"]].get("cold_ui_words",[])}
                assert expected<=actual,("stable cold menu incomplete",cp["label"],expected-actual)
    return dict(timeline=timeline,alpha=alpha,zh=zh,keys=set(zh),events=len(events),visible={key:0 for key in zh})


def paint(data,words,palette,model):
    for word in words:
        x,y,width=word["X"]*2,word["Y"]*2,word["Width"]*2
        bg,fg=palette[word["Background"]],palette[word["Foreground"]]
        assert 0<=x<x+width<=640 and 0<=y<y+16<=400
        for yy in range(y,y+16):data[(yy*640+x)*4:(yy*640+x+width)*4]=bytes([*bg,255])*width
        for i,ch in enumerate(model["zh"][word["Key"]]):
            alpha=model["alpha"][ch]
            for yy in range(16):
                for xx in range(16):
                    v=alpha[yy*16+xx]
                    if not v:continue
                    at=((y+yy)*640+x+i*16+xx)*4
                    for c in range(3):data[at+c]=(fg[c]*v+data[at+c]*(255-v)+127)//255


def negative(probe,output,en_name,zh_name):
    import shutil
    from contextlib import redirect_stdout
    import io
    a,b=[read(output/n/"receipt.json") for n in (en_name,zh_name)]
    source=Path(a["cold_ui"]["input_root"])
    target=output/"prompt-negatives";assert not target.exists();target.mkdir()
    results=[]
    for name in ["background","position","caller","menu-signature"]:
        folder=target/name;shutil.copytree(source,folder)
        config=read(folder/"bindings.json")
        if name=="background":config["Bindings"][0]["Background"]^=1
        elif name=="position":config["Bindings"][0]["X"]+=8
        elif name=="caller":config["Bindings"][0]["Caller"]["Off"]+=1
        else:
            binding=next(row for row in config["Bindings"] if row["Button"])
            binding["MenuSignature"]="0"*64
        (folder/"bindings.json").write_text(json.dumps(config,ensure_ascii=False,indent=2)+"\n")
        modified=[]
        for run in (a,b):
            copy=run.copy();meta=run["cold_ui"].copy();meta["files"]=meta["files"].copy()
            # /out 是同一個工作目錄的可寫別名；收據仍使用唯讀 /probe 定位。
            relative=folder.relative_to(output)
            meta["input_root"]=str(source.parent/relative)
            meta["files"]["bindings.json"]=sha((folder/"bindings.json").read_bytes());copy["cold_ui"]=meta;modified.append(copy)
        try:
            with redirect_stdout(io.StringIO()):model(probe,*modified)
        except AssertionError:results.append(dict(name=name,rejected=True))
        else:raise AssertionError("應拒絕卻通過："+name)
    (target/"results.json").write_text(json.dumps(dict(cases=results,checker_sha256=sha(Path(__file__).read_bytes())),indent=2)+"\n")
    print(json.dumps(results))


if __name__=="__main__":
    if sys.argv[1]=="negative":negative(Path(sys.argv[2]),Path(sys.argv[3]),sys.argv[4],sys.argv[5])
