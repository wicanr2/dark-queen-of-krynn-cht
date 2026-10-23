"""由 MZ 原版觀測、正式譯表及短標籤校讀稿建立冷讀提示輸入。"""
import csv
import hashlib
import json
import sys
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text())


def catalog(path):
    rows=path.read_text().splitlines()
    assert rows[0]=="key\ttext"
    result={}
    for line in rows[1:]:
        key,text=line.split("\t")
        assert key not in result and text
        result[key]=text
    return result


def write(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def prompt_mask_width(source,button=False):
    width=len(source if button else source.rstrip(" "))*8
    if not button and source=="load which game:":width-=4
    return width


def prepare(text,study,output,observe_name):
    assert not output.exists()
    observed=study/observe_name/"receipt.json"
    trace=read(observed)
    assert trace["cold_boot"] and not trace["snapshot_loaded"]
    assert trace["source_commit"]=="f79eab6db8c64a524a06535e53e5d32b0bbcf7c8"
    assert trace["pending_calls"]==trace["pending_fills"]==trace["pending_wrappers"]==trace["pending_boot_menus"]==0
    en,zh=catalog(text/"en.tsv"),catalog(text/"zh-TW.tsv")
    review=list(csv.DictReader((text/"load-ui-review.tsv").open(),delimiter="\t"))
    assert {r["key"] for r in review}=={"load.current","load.previous"}
    by_raw={r["en"]:r for r in review}
    output.mkdir()
    words_en,words_zh,origins,bindings={}, {}, {}, []
    chosen=[]
    for call in trace["calls"]:
        source=call["vararg_1_candidate"]["text"] if call["format"]["text"]=="%s" else call["format"]["text"]
        if call["step"]<261100000 or call["step"]>=301100000:continue
        if source in by_raw or source in ["Exit","load from where? ","load which game:","Loading...Please Wait"]:
            if source not in [s for s,c in chosen]:chosen.append((source,call))
    assert len(chosen)==6
    menus={}
    for source,call in chosen:
        if source in by_raw:
            row=by_raw[source];key=row["key"];translation=row["zh-TW"]
            origin=dict(review_key=key,review=row)
        else:
            matches=[k for k,v in en.items() if k.startswith("ui.") and v.rstrip(" ")==source.rstrip(" ")]
            assert len(matches)==1,(source,matches)
            key=matches[0];translation=zh[key]
            origin=dict(formal_key=key,en=en[key],zh=translation,rule="rstrip-space" if en[key]!=source else "exact")
        words_en[key],words_zh[key],origins[key]=source,translation,origin
        glyphs=call["glyph_calls"]
        first=glyphs[0];assert first["stack"][2:4]==[first["ds_ca14"],first["ds_ca12"]]
        assert call["step"]<call["first_glyph"]==first["step"]<call["return_step"]
        button=call["caller"]==dict(Seg=0xCEB,Off=0x1BE)
        group="source" if button or source=="load from where? " else "slots" if source=="load which game:" else "loading"
        binding=dict(Key=key,Group=group,SourceSHA256=sha(source.encode()),FormatSHA256=sha(call["format"]["text"].encode()),
                     Caller=call["caller"],UpperCaller=dict(Seg=0,Off=0),UpperFormatSHA256="",MenuSignature="",
                     RawX=call["stack"][3],RawY=call["stack"][2],X=first["stack"][3],Y=first["stack"][2],
                     Width=prompt_mask_width(source,button),Background=(call["stack"][4]>>4)&15,Button=button)
        if button:
            menu=trace["menus"][call["menu_index"]]
            binding["MenuSignature"]=menu["Signature"];menus[menu["Signature"]]="source"
        else:
            wrapper=trace["wrappers"][call["wrapper_index"]]
            binding["UpperCaller"]=wrapper["caller"]
            binding["UpperFormatSHA256"]=sha(wrapper["format"]["text"].encode())
            binding["Color"]=call["stack"][4]
        assert len(translation)*8<=binding["Width"] and binding["Y"]==189
        bindings.append(binding)
    for menu in trace["menus"]:
        buttons=menu["Buttons"]
        if buttons and all(len(bytes.fromhex(b["SourceHex"]))==1 and b["RawY"]==8094 for b in buttons):
            assert all(chr(bytes.fromhex(b["SourceHex"])[0]) in "ABCDEFGHIJ" for b in buttons)
            menus[menu["Signature"]]="slots"
    assert len(menus)==2
    for name,rows in [("en.tsv",words_en),("zh-TW.tsv",words_zh)]:
        (output/name).write_text("key\ttext\n"+"".join(k+"\t"+v+"\n" for k,v in sorted(rows.items())),encoding="utf-8")
    write(output/"bindings.json",dict(Bindings=bindings,Menus=menus))
    write(output/"provenance.json",dict(draft=True,observed_path=str(observed),observed_sha256=sha(observed.read_bytes()),
        origins=origins,source_files={n:sha((text/n).read_bytes()) for n in ["en.tsv","zh-TW.tsv","load-ui-review.tsv"]},
        glyph_evidence=[dict(key=b["Key"],call_step=c["step"],first_glyph=c["first_glyph"],glyph_calls=c["glyph_calls"]) for b,(s,c) in zip(bindings,chosen)],
        limits="六段呈現文字；槽位字母、檔名、TDQK／DKK 識別與原版按鍵均保持原樣"))
    print(json.dumps(dict(words=len(words_en),bindings=len(bindings),menus=len(menus)),ensure_ascii=False))


def case(probe,study,output,base,name):
    import shutil
    request_path=study/("request-"+name+"-r1.json")
    request=read(request_path)
    observed=study/("observe-"+name+"-r1")/"receipt.json"
    trace=read(observed)
    assert trace["cold_boot"] and not trace["snapshot_loaded"] and request["start_steps"]==0
    assert trace["checkpoints"][-1]["indexed_sha256"]=="d7eec5b094e4265a627d2b61333d3bc7d339572431e281ac29b533e10c76ae67"
    boot=read(output/"boot.json")
    boot["Actions"]=[dict(At=a["at"],End=a["end"],Kind=a["kind"],Key=a["key"],Label=a["label"]) for a in request["actions"]]
    write(output/"boot.json",boot)
    assert not (output/"ui-inputs").exists()
    shutil.copytree(base/"ui-inputs",output/"ui-inputs")
    p=output/"ui-inputs/provenance.json";origin=read(p)
    origin["validation_trace"]=dict(path=str(observed),sha256=sha(observed.read_bytes()))
    write(p,origin)
    write(output/"case-source.json",dict(name=name,request=str(request_path),request_sha256=sha(request_path.read_bytes()),observed=str(observed),observed_sha256=sha(observed.read_bytes())))
    print(json.dumps(dict(case=name,boot_actions=len(boot["Actions"]))))


def evidence(project,primary,cancel,focus):
    import shutil
    probe=project/"workplace/probe"
    roots=[probe/primary,probe/cancel,probe/focus]
    reports=[]
    for root,count in zip(roots,[12,17,18]):
        cold,game=read(root/"cold-check.json"),read(root/"gameplay-check.json")
        assert cold["original_checkpoints_equal"]==count
        assert cold["checker_sha256"]==sha((project/"tools/cold_load.py").read_bytes())
        assert cold["cold_prompt_model_sha256"]==sha((project/"tools/load_prompt_check.py").read_bytes())
        assert all(cold["cold_prompt_visible_frames"].values()) and len(cold["cold_prompt_visible_frames"])==6
        assert game["all_submitted_pixels_equal_expected"] and game["field_lifetime_model_equal"]
        assert game["checker_sha256"]==sha((project/"tools/ui_list_live_check.py").read_bytes())
        for name in cold["runs"]:
            events=dict(line.split() for line in (root/(name+"-memory-events.txt")).read_text().splitlines())
            assert events["oom"]==events["oom_kill"]=="0"
        reports.append(dict(root=str(root.relative_to(project)),cold=cold,gameplay=game))
    negatives=read(roots[0]/"prompt-negatives/results.json")
    assert len(negatives["cases"])==4 and all(case["rejected"] for case in negatives["cases"])
    assert negatives["checker_sha256"]==sha((project/"tools/load_prompt_check.py").read_bytes())
    legacy=read(roots[0]/"legacy-check.json")
    assert legacy["original_checkpoints_equal"]==16 and legacy["real_gpu_readback_frames"]==1306
    assert legacy["all_submitted_pixels_equal_expected"] and legacy["field_lifetime_model_equal"]
    assert legacy["checker_sha256"]==sha((project/"tools/ui_list_live_check.py").read_bytes())
    guards=(roots[0]/"runtime-guards/results.tsv").read_text().splitlines()
    assert {line.split("\t")[0] for line in guards}=={"source","quiz","time","role","snapshot"}
    checker_negatives=read(roots[0]/"checker-negatives/results.json")
    assert len(checker_negatives["cases"])==4 and all(case["rejected"] for case in checker_negatives["cases"])
    assert checker_negatives["checker_sha256"]==sha((project/"tools/cold_load.py").read_bytes())
    snapshot=roots[0]/"tool-snapshots";assert not snapshot.exists();snapshot.mkdir()
    names=["load_prompt_inputs.py","load_prompt_check.py","ui_cold_prompts.go","cold_load.py","cold_load_probe.go","cold-load.sh",
           "early_text_live.go","ui_list_live.go","ui_list_live_check.py","ui_list_inputs.py","ui_list_paragraphs.go",
           "ui_journal_reader.go","ui_journal_illustrations.go","ui_menu_source.go","oracle_video_observer.go",
           "ui_context_probe.go","ui_context_check.py","ui-context.sh","ui-list-live.sh","early-live.sh",
           "ui_journal_reader_check.py","ui_journal_illustrations_check.py","camp_live_inputs.py","menu_glyphs.py"]
    tools={}
    for name in names:
        p=project/"tools"/name;shutil.copyfile(p,snapshot/name);tools[name]=sha(p.read_bytes())
    for name in ["ui-list-live","cold-load-probe","ui-context-probe"]:shutil.copyfile(probe/name,snapshot/name)
    def fingerprint(path):
        h=hashlib.sha256()
        with path.open("rb") as stream:
            while block:=stream.read(1<<20):h.update(block)
        return dict(path=str(path.relative_to(project)),bytes=path.stat().st_size,sha256=h.hexdigest())
    artifacts=[]
    for root in roots:
        artifacts += [fingerprint(p) for p in sorted(root.rglob("*")) if p.is_file() and p.name!="evidence.json"]
    study=probe/"load-prompts-20261023"
    artifacts += [fingerprint(p) for p in sorted(study.rglob("*")) if p.is_file()]
    sources=[project/"workplace/translation"/n for n in ["en.tsv","zh-TW.tsv","glossary.tsv","catalog.json","glossary-additions.tsv","load-ui-review.tsv"]]
    sources += [probe/"cold-load-20261023-r3/evidence.json",project/"workplace/input/dos/drkqueen/DQK.EXE"]
    result=dict(draft=True,source_commit="f79eab6db8c64a524a06535e53e5d32b0bbcf7c8",tools=tools,
        artifacts=artifacts,sources=[fingerprint(p) for p in sources],reports=reports,negatives=negatives,
        legacy=legacy,runtime_guards=guards,checker_negatives=checker_negatives,
        docker_images=dict(go="sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581",
                           python="sha256:44d0742ca1061bcd453440cdce925afa31c5324e115fca1334da0e364f0e2c48"),
        failed_attempts=["load-prompts-20261023/observe-r1、control-r1 從舊快照開始；畫面相同但狀態不同，只作診斷",
                         "load-prompts-live-20261023/en-r1、zh-r1 在同頁選單重畫時刪除按鈕；不作成功證據"],
        receipt_scope_note="GUI 收據的通用 scope 字段沿用前批文字；本批六項提示以 cold_ui、獨立原版模型與本索引 reports 為準",
        rights="原版、存檔、完整詞條、字模、畫格與二進位只留本機 workplace，不加入 Git",
        limits="六段讀檔呈現文字及已驗取消／反白路徑；沒有 DKK 角色匯入、全部槽位、實體鍵盤、正式入口或完整中文化聲明")
    target=roots[0]/"evidence.json";assert not target.exists();write(target,result)
    print(json.dumps(dict(artifacts=len(artifacts),tools=len(tools),reports=len(reports))))


if __name__=="__main__":
    if sys.argv[1]=="case":case(*map(Path,sys.argv[2:6]),sys.argv[6])
    elif sys.argv[1]=="evidence":evidence(Path(sys.argv[2]),*sys.argv[3:6])
    else:prepare(*map(Path,sys.argv[1:4]),sys.argv[4])
