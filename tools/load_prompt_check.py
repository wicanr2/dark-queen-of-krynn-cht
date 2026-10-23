"""從獨立 MZ 觀測建立冷讀提示模型，提供 cold_load.py 逐幀比對。"""
import base64
import csv
import hashlib
import json
from pathlib import Path
import sys
from PIL import Image


def sha(data):return hashlib.sha256(data).hexdigest()
def read(path):return json.loads(path.read_text())
def catalog(path):return dict(line.split("\t",1) for line in path.read_text().splitlines()[1:])
def snapshot(words):return sorted(words.values(),key=lambda w:(w["Y"],w["X"]))
def intersects(w,r):return w["X"]<r[0]+r[2] and w["X"]+w["Width"]>r[0] and w["Y"]<r[1]+r[3] and w["Y"]+8>r[1]
def native(v):return v if v<400 else (v-8000)*2


def model(probe,a,b,expected_only=False):
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
    startup_review={r["key"]:r for r in csv.DictReader((formal/"startup-ui-review.tsv").open(),delimiter="\t")} if origin.get("startup_extension") else {}
    for name,digest in origin["source_files"].items():assert sha((formal/name).read_bytes())==digest
    for key,source in origin["origins"].items():
        if "formal_key" in source:
            root=source["formal_key"]
            assert (source["en"],source["zh"])==(main_en[root],main_zh[root])
            assert en[key]==(main_en[root].rstrip(" ") if source["rule"]=="rstrip-space" else main_en[root])
            assert zh[key]==main_zh[root]
        elif "startup_review_key" in source:
            row=startup_review[source["startup_review_key"]]
            assert row==source["review"] and (en[key],zh[key])==(row["en"],row["zh-TW"])
        else:
            row=review[source["review_key"]]
            assert row==source["review"] and (en[key],zh[key])==(row["en"],row["zh-TW"])
    trace_path=Path(origin["observed_path"])
    assert trace_path.resolve().is_relative_to(probe.resolve()) and sha(trace_path.read_bytes())==origin["observed_sha256"]
    trace=read(trace_path)
    assert trace["cold_boot"] and not trace["snapshot_loaded"] and not trace["pending_boot_menus"]
    assert len(en)==len(zh)==len(config["Bindings"]) in (6,15)
    calls_by_step={c["step"]:c for c in trace["calls"]}
    evidence={row["key"]:row for row in origin["glyph_evidence"]}
    for binding in config["Bindings"]:
        key=binding["Key"]
        call=calls_by_step[evidence[key]["call_step"]]
        assert call.get("glyph_calls")==evidence[key]["glyph_calls"]
        assert call["step"]<evidence[key]["first_glyph"]==call["first_glyph"]<call["return_step"]
        width=len(en[key] if binding["Button"] else en[key].rstrip(" "))*8
        if not binding["Button"] and en[key]=="load which game:":width-=4
        assert binding["SourceSHA256"]==sha(en[key].encode()) and binding["Width"]==width
        assert binding["X"]==native(binding["RawX"]) and binding["Y"]==native(binding["RawY"])
        if not key.startswith("startup."):assert binding["Y"]==189
        assert len(zh[key])*8<=binding["Width"]
        assert binding["Caller"]==call["caller"] and [binding["RawY"],binding["RawX"]]==call["stack"][2:4]
        if key.startswith("startup."):
            assert binding["Background"]==23
        else:assert binding["Background"]==(call["stack"][4]>>4)&15
        if not binding["Button"] and binding["Background"]==7:
            cp=next(cp for cp in trace["checkpoints"] if cp["step"]>=call["return_step"])
            original=Image.open(trace_path.parent/(cp["label"]+".png")).convert("RGB")
            colors=set(original.crop((binding["X"],189,binding["X"]+width,197)).getdata())
            assert colors=={tuple(cp["palette"][0]),tuple(cp["palette"][7])},("native prompt border",key)
        if call.get("glyph_calls"):
            assert [binding["Y"],binding["X"]]==call["glyph_calls"][0]["stack"][2:4]
        else:assert key.startswith("startup.") and origin.get("startup_extension")
        assert binding["FormatSHA256"]==sha(call["format"]["text"].encode())
        if binding["Button"]:
            assert binding["MenuSignature"]==trace["menus"][call["menu_index"]]["Signature"]
            assert config["Menus"][binding["MenuSignature"]]==binding["Group"]
        elif binding["UpperCaller"]!={"Seg":0,"Off":0}:
            assert binding["Color"]==call["stack"][4]
            wrapper=trace["wrappers"][call["wrapper_index"]]
            assert binding["UpperCaller"]==wrapper["caller"]
            assert binding["UpperFormatSHA256"]==sha(wrapper["format"]["text"].encode())
        else:
            assert key=="startup.quiz-enter" and call["caller"]=={"Seg":0x266D,"Off":0x11F}
            assert call["format"]["text"]=="%s" and en[key]=="Enter " and binding["Color"]==0x8b
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
    traces=[trace]
    if origin.get("continuation_trace"):
        continuation=origin["continuation_trace"];path=Path(continuation["path"])
        assert path.resolve().is_relative_to(probe.resolve()) and sha(path.read_bytes())==continuation["sha256"]
        post=read(path);assert post["cold_boot"] and not post["snapshot_loaded"] and post["request"]["start_steps"]==355000000
        traces.append(post)
    video=None
    if origin.get("page_sync"):
        proof=origin["page_sync"];path=Path(proof["path"])
        assert path.resolve().is_relative_to(probe.resolve()) and sha(path.read_bytes())==proof["sha256"]
        video=read(path)
        assert video["cold_boot"] and not video["snapshot_loaded"] and len(video["checkpoints"])==19
        assert not video["pending_calls"] and not video["pending_fills"]
        video_calls={c["step"]:c for c in video["calls"]}
        video_fills={f["step"]:f for f in video["fill_events"]}
        changes=video["display_changes"]
        for e in changes:
            if e["step"]<220000000:continue
            l=e["layout"]
            assert l["Mode"]==19 and l["Unchained"] and l["Pitch"]==80 and l["DisplayStart"] in (0,16384)
        def page_at(step):return next(e["layout"]["DisplayStart"] for e in reversed(changes) if e["step"]<=step)
        def visible_from(page,step):
            if page_at(step)==page:return step
            return next(e["step"] for e in changes if e["step"]>step and e["layout"]["DisplayStart"]==page)
        def target(event):
            pages=event["video_pages"];assert len(pages)==1 and sum(pages.values())>0
            page=int(next(iter(pages)));assert page in (0,16384)
            return page
    schedule=[]
    for part in traces:
      for event in part["boot_menu_events"]:schedule.append((event["step"],"menu",event))
      for event in part["fill_events"] or []:
        schedule.append((event["converted_step"],"clear",event))
        schedule.append((event["return_instruction_step"],"clear-return",event))
      for call in part["calls"]:
        source=call["vararg_1_candidate"]["text"] if call["format"]["text"]=="%s" else call["format"]["text"]
        if len(traces)>1 and call["step"]>=355000000:
            format=call["format"]["text"]
            if format in ("%s","%c") or "%" not in format:
                width=8 if format=="%c" else len(source)*8
                schedule.append((call["step"],"overwrite",dict(caller=call["caller"],source_sha256=sha(source.encode()),rect=[native(call["stack"][3]),native(call["stack"][2]),width,8])))
            continue
        matches=[]
        for binding in config["Bindings"]:
            if binding["Caller"]!=call["caller"] or [binding["RawY"],binding["RawX"]]!=call["stack"][2:4]:continue
            if binding["SourceSHA256"]!=sha(source.encode()) or binding["FormatSHA256"]!=sha(call["format"]["text"].encode()):continue
            if "Color" in binding and binding["Color"]!=call["stack"][4]:continue
            if binding["Button"]:
                assert call["menu_index"]>=0
                if part["menus"][call["menu_index"]]["Signature"]!=binding["MenuSignature"]:continue
            elif binding["UpperCaller"]!={"Seg":0,"Off":0}:
                wrapper=part["wrappers"][call["wrapper_index"]]
                if wrapper["caller"]!=binding["UpperCaller"] or sha(wrapper["format"]["text"].encode())!=binding["UpperFormatSHA256"]:continue
                assert wrapper["step"]<call["step"]<call["return_step"]<wrapper["return_step"]
            matches.append(binding)
        assert len(matches)<=1
        if matches:
            if origin.get("startup_extension"):
                assert any(lo<=call["step"]<call["return_step"]<=hi for lo,hi in config["FineWindows"]),("missing caption source interval",call["step"])
            schedule.append((call["step"],"word",(call,matches[0])))
            if video:
                v=video_calls[call["step"]]
                assert all(v[k]==call[k] for k in ("caller","stack","format","return_step","first_glyph"))
                schedule.append((call["return_step"],"complete",(call,matches[0],target(v))))
    words={};affected=set();events=[];timeline=[];records={};histories=[];waits=[];wait_histories=[]
    def erase(rect):
        removed=[p for p,w in words.items() if intersects(w,rect)]
        for p in removed:del words[p]
        return bool(removed)
    for step,kind,data in sorted(schedule,key=lambda e:e[0]):
        waits=[end for end in waits if end>step]
        if len(traces)>1 and step>=355000000 and not words and not affected and not waits:continue
        event=None
        if kind=="menu":
            menu=data["menu"];pane=config["Menus"].get(menu["Signature"],"") if data["valid"] else ""
            footer=data["valid"] and all(btn["RawY"]==8094 for btn in menu["Buttons"])
            for p,w in list(words.items()):
                if w["Group"] in ("role-name","party-name","quiz"):continue
                if not footer or (w.get("Button") and not pane) or w["Group"]=="loading" or (pane and w["Group"]!=pane):del words[p]
            event=dict(step=step,kind="menu-entry",detail=dict(menu=menu,valid=data["valid"],pane=pane),words=snapshot(words))
        elif kind=="clear":
            rect=data["native_rect"]
            if erase(rect):
                if origin.get("startup_extension") and step<355000000:
                    assert any(lo<=data["step"]<data["return_instruction_step"]<=hi for lo,hi in config["FineWindows"]),("missing caption clear interval",data["step"])
                affected.add(data["step"])
                event=dict(step=step,kind="native-clear",detail=dict(entry_step=data["step"],rect=rect),words=snapshot(words))
        elif kind=="clear-return":
            if data["step"] in affected:
                affected.remove(data["step"])
                detail=dict(entry_step=data["step"])
                if video:
                    v=video_fills[data["step"]]
                    assert v["native_rect"]==data["native_rect"] and v["return_instruction_step"]==step
                    page=target(v);detail["target_page"]=page
                    waits.append(visible_from(page,step))
                event=dict(step=step,kind="native-clear-return",detail=detail,words=snapshot(words))
        elif kind=="overwrite":
            if erase(data["rect"]):event=dict(step=step,kind="native-text-overwrite",detail=data,words=snapshot(words))
        elif kind=="complete":
            call,binding,page=data
            start=visible_from(page,step)
            end=next((e["step"] for e in changes if e["step"]>start and e["layout"]["DisplayStart"]!=page),400000001)
            records[binding["Key"]]=(start,end)
            event=dict(step=step,kind="print-complete",detail=dict(call_step=call["step"],key=binding["Key"],target_page=page),words=snapshot(words))
        else:
            call,binding=data
            assert call["step"]<call["first_glyph"]<call["return_step"]
            word=dict(X=binding["X"],Y=binding["Y"],Width=binding["Width"],Key=binding["Key"],Group=binding["Group"],Foreground=call["stack"][4]&15,Background=binding["Background"])
            if binding["Button"]:word["Button"]=True
            erase([word["X"],word["Y"],word["Width"],8]);words[word["X"],word["Y"]]=word
            records[binding["Key"]]=None
            event=dict(step=step,kind="word-before-glyph",detail=dict(key=binding["Key"],source_sha256=binding["SourceSHA256"],format_sha256=binding["FormatSHA256"],caller=call["caller"],word=word),words=snapshot(words),first_glyph=call["first_glyph"])
        if event:
            if not event["words"]:event["words"]=None
            events.append(event);timeline.append((step,event["words"] or [],bool(affected),len(events)))
            histories.append(dict(records));wait_histories.append(list(waits))
    assert not words and not affected
    for run in (() if expected_only else (a,b)):assert run["cold_ui"]["events"]==events
    for run in (() if expected_only else (a,b)):
        frames={f["step"]:f for f in run["cold_frames"]}
        for cp in run["cold_checkpoints"]:
            previous=[e for e in trace["boot_menu_events"] if e["step"]<cp["step"] and e["valid"]]
            if not previous:continue
            pane=config["Menus"].get(previous[-1]["menu"]["Signature"])
            if pane:
                expected={binding["Key"] for binding in config["Bindings"] if binding["Group"]==pane}
                actual={w["Key"] for w in frames[cp["step"]].get("cold_ui_words",[])}
                assert expected<=actual,("stable cold menu incomplete",cp["label"],expected-actual)
    return dict(timeline=timeline,alpha=alpha,zh=zh,keys=set(zh),events=len(events),visible={key:0 for key in zh},fine_windows=config.get("FineWindows",[]),
                page_sync=bool(video),page_changes=video["display_changes"] if video else [],print_history=histories,wait_history=wait_histories)


def pending_at(model,frame,count,words,pending):
    if not model["page_sync"]:return pending
    step=frame["step"]
    page=next(e["layout"]["DisplayStart"] for e in reversed(model["page_changes"]) if e["step"]<=step)
    # 所有冷讀提示在 400M 前撤除；其後切頁由既有遊戲內模型驗證。
    if 220000000<=step<=400000000:assert frame.get("cold_ui_page",0)==page,("cold display page",step)
    if not count:return pending
    records=model["print_history"][count-1]
    if any(end>step for end in model["wait_history"][count-1]):return True
    return pending or any(records[w["Key"]] is None or not records[w["Key"]][0]<=step<records[w["Key"]][1] for w in words)


def paint(data,words,palette,model):
    for word in words:
        x,y,width=word["X"]*2,word["Y"]*2,word["Width"]*2
        bg,fg=palette[word["Background"]],palette[word["Foreground"]]
        assert 0<=x<x+width<=640 and 0<=y<y+16<=400
        if word["Key"].startswith("startup."):
            # 0x8? 的高四位不是此畫面的實際背景；原版底圖使用索引 23。
            # 索引 23 的 RGB 會隨介面換色；直接從原文畫格的平坦底色取得。
            from collections import Counter
            counts=Counter(tuple(data[(yy*640+xx)*4:(yy*640+xx)*4+3]) for yy in range(y,y+16) for xx in range(x,x+width))
            bg=counts.most_common(1)[0][0];original=set(counts)
            allowed={tuple(bg),tuple(fg),tuple(palette[0]),tuple(palette[15])}
            if word.get("Button") and word["Group"]=="opening":
                # 原版選中 Play：P 用 11，lay 用 3；亮色只准在第一個原文字格。
                # 比對來源為 cold-color-diagnostic.json 的 241028000 原文畫格。
                rest={tuple(data[(yy*640+xx)*4:(yy*640+xx)*4+3]) for yy in range(y,y+16) for xx in range(x+16,x+width)}
                assert rest<=allowed,("native opening hotkey bounds",word["Key"],rest-allowed)
                allowed.add(tuple(palette[word["Foreground"]|8]))
            assert word["Background"]==23 and tuple(bg) in original and original<=allowed,("native caption background",word["Key"],original-allowed)
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
