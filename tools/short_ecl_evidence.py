"""短敘事的來源審查、實際畫格抽查及本機索引；不修改實測輸入。"""
import json
from pathlib import Path
import shutil
import sys

from literal_catalog import catalog, read, sha, write


def source_review(root,output):
    handler=read(output/"ida-handler-r2.json");operand=read(output/"ida-operand-r1.json")
    blocks=[("code.bin",0x1cd3,0x1d8d,"c61ccaba966f4c04eea49304ea633c61c02566cd8ca8e93105412d50e7f239c9",handler),
            ("operand-code.bin",0x13,0x112,"c6f1c1c8cb204e32aa000a8ca180da3a23431f5d2a0e799cf4e65792269ef6ff",operand)]
    import hashlib
    for name,lo,hi,h,r in blocks:
        path=output/"dump-r4"/name;raw=path.read_bytes()
        assert r["ida_version"]=="9.4" and r["input_sha256"]==sha(path)
        assert (r["function"]["start"],r["function"]["end"])==(lo,hi)
        assert hashlib.sha256(raw[lo:hi]).hexdigest()==h
        for item in r["items"]:
            b=bytes.fromhex(item["bytes"]);assert raw[item["ea"]:item["ea"]+len(b)]==b
    raw=(output/"dump-r4/operand-code.bin").read_bytes()
    assert raw[0x68:0x72]==bytes.fromhex("01000200030080008100")
    assert raw[0x72:0x7c]==bytes.fromhex("7c007c007c009100c600")
    tests=[json.loads(l) for l in (output/"guard-tests.jsonl").read_text().splitlines()]
    assert not any(r["Action"] in ("fail","skip") for r in tests)
    passed=[r["Test"] for r in tests if r["Action"]=="pass" and "/" in r.get("Test","")]
    assert len(passed)==9 and any(r["Action"]=="pass" and r.get("Test")=="TestShortECLSourceGuard" for r in tests)
    old,new=[read(p/"inputs.json") for p in (root/"workplace/probe/literal-catalog-20261024/inputs-r3",output/"inputs-r1")]
    en=catalog(output/"inputs-r1/en.tsv");records=[]
    for name in ("battle-text-20261024/observe-route-r1/receipt.json","pane-render-20261022/observe-palace-journal-r1/receipt.json"):
        path=root/"workplace/probe"/name;trace=read(path)
        for p in trace["paragraphs"] or []:
            matches=lambda config:[b for b in config["Paragraphs"] if en[b["Key"]]==p["source"]["text"] and b["Caller"]==p["caller"]
                and b["NativeBox"]==p["native_box"] and [b[k] for k in ("Foreground","Background","Clear")]==[p[k] for k in ("foreground","background","clear")]]
            assert matches(old)==matches(new)
        records.append(dict(path=name,sha256=sha(path),paragraphs=len(trace["paragraphs"] or [])))
    write(output/"source-review.json",dict(ida_functions=2,source_cycles=read(output/"native-source-check.json")["handler_cycles"],
        guard_cases=passed,old_selections=records,limits="80h 原位元串與本輪四個正常來源已證實；其他型別只作靜態分支辨識與測試拒絕，不宣稱自然變數路徑完成。舊選譯相同不等於重跑舊 GPU。"))


def regression_inputs(probe,output):
    source=probe/"battle-text-20261024/inputs-arrival-r3";target=output/"inputs-arrival-sparse-r1"
    assert not target.exists();shutil.copytree(source,target)
    config=read(target/"inputs.json");config["fine_windows"]=[]
    (target/"inputs.json").write_text(json.dumps(config,ensure_ascii=False,indent=2)+"\n")
    assert all((source/p.name).read_bytes()==p.read_bytes() for p in target.iterdir() if p.name!="inputs.json")
    old=read(source/"inputs.json");assert {k:v for k,v in config.items() if k!="fine_windows"}=={k:v for k,v in old.items() if k!="fine_windows"}
    fixed=read(output/"arrival-run-r4.json")
    fixed["input_path"]=output.name+"/"+target.name;fixed["inputs"]={p.name:sha(p) for p in target.iterdir()}
    write(output/"arrival-run-r5.json",fixed)
    write(output/"arrival-sparse-input-check.json",dict(original="battle-text-20261024/inputs-arrival-r3",executed=fixed["input_path"],
        changed_file="inputs.json",changed_field="fine_windows",unchanged_files=14,
        limits="原 r1 使用 fine=false 卻保留細驗宣告，驗證已拒絕；r2 以明列空區間的新輸入重播，來源紀錄及其餘檔案不變。"))


def guard_recheck(output):
    from ui_list_live_check import check_short_ecl_sources
    records=[]
    for row in read(output/"short-data-guards.json")["cases"]:
        p=output/("negative-"+row["case"])
        try:check_short_ecl_sources(p,read(p/"inputs.json"),read(p/"provenance.json"),catalog(p/"en.tsv"),catalog(p/"zh-TW.tsv"),read(p/"glyphs-16.json"))
        except AssertionError as e:assert str(e)==row["reason"];records.append(row)
        else:raise AssertionError(row["case"])
    write(output/"short-data-guards-final.json",dict(cases=records,checker_sha256=sha(Path(__file__).with_name("ui_list_live_check.py"))))


def visibility(output):
    source=read(output/"observe-bar-r3/receipt.json");pairs=[]
    for i in range(4):
        a,b=source["events"][5*i],source["events"][5*i+4]
        assert a["caller"]==b["caller"] and all(a["regs"][k]==b["regs"][k] for k in ("SS","SP","BP"))
        pairs.append(dict(entry=a["step"],retf=b["step"],caller=a["caller"],ss=a["regs"]["SS"],sp=a["regs"]["SP"]))
    run=read(output/"zh-r1/receipt.json");records=[]
    for key in ("ecl.972b4ea2b9612d562204","ecl.a3bf0c2952973d155e40"):
        index,event=next((i,e) for i,e in enumerate(run["list_events"]) if e["Kind"]=="paragraph-before-glyph" and e["detail"]["page"]["Key"]==key)
        shown=[f for f,s in zip(run["frames"],run["list_frames"]) if not f["held"] and key in (s.get("paragraph") or {}).get("Components",[])]
        assert shown
        waiting=[f for f,s in zip(run["frames"],run["list_frames"]) if s["list_event_count"]>index and event["Step"]<=f["step"]<shown[0]["step"]]
        assert all(f["held"] for f in waiting)
        records.append(dict(key=key,source_step=event["Step"],first_glyph=event["first_glyph"],first_visible=shown[0]["step"],
            visible_frames=len(shown),held_before_first_visible=len(waiting)))
    write(output/"visibility-review.json",dict(handler_stack_pairs=pairs,texts=records,
        limits="酒館標題在首字形前取得，場景過渡先保留完整前畫面，稍後才可見；不把攔截步數當成中文顯示步數。舊路徑稀疏回歸不作無閃爍聲明。"))


def scope_audit(root,output):
    texts=root/"workplace/translation";en,zh=catalog(texts/"en.tsv"),catalog(texts/"zh-TW.tsv")
    current=catalog(output/"inputs-r1/en.tsv");translated={k for k in en if k in zh and k.startswith("ecl.")}
    fragments={f["key"] for g in read(texts/"passage-candidates.json")["groups"] for s in g["sources"] for f in s["fragments"]}
    unbound=translated-set(current);pending_fragments=unbound&fragments
    references={k for k in unbound if "JOURNAL ENTRY" in en[k]}
    assert unbound==pending_fragments|references and not (pending_fragments&references)
    frozen=output/"programs-r4/ecl_source_probe.go";now=root/"tools/ecl_source_probe.go"
    assert frozen.read_text().splitlines()[1:]==now.read_text().splitlines()[1:]
    write(output/"ecl-scope-audit.json",dict(translated=len(translated),catalog_keys=len(translated&set(current)),
        unbound=len(unbound),fragment_keys=sorted(pending_fragments),reference_keys=sorted(references),
        probe_comment_correction=dict(executed_sha256=sha(frozen),current_sha256=sha(now),only_first_comment_line_changed=True),
        limits="目錄鍵集合的差額，不是剩餘玩家流程數；十個引用排除候選包含已接手札 65，實際未在目錄的引用候選為九個。"))


def review(output,revision="r2"):
    from PIL import Image,ImageDraw
    records=[]
    a,b=[read(output/(lang+"-r1/receipt.json")) for lang in ("en","zh")]
    points=[(cp["label"],cp["step"]) for cp in b["checkpoints"]]
    for label,step in points:
        panel=Image.new("RGB",(1280,420),"#202020");draw=ImageDraw.Draw(panel);sources=[]
        for i,(lang,r) in enumerate((("en",a),("zh",b))):
            frame=next(f for f in r["frames"] if f["step"]==step);assert not frame["held"]
            path=output/(lang+"-r1")/frame["File"]
            panel.paste(Image.open(path).convert("RGB"),(640*i,20));draw.text((640*i+4,2),label+" / "+lang,fill="white")
            sources.append(dict(path=str(path.relative_to(output)),sha256=sha(path),step=step))
        path=output/("review-"+revision+"-"+label+".png");assert not path.exists();panel.save(path)
        records.append(dict(label=label,sources=sources,panel=path.name,sha256=sha(path)))
    arrival=[read(output/("arrival-"+lang+"-"+revision+"/receipt.json")) for lang in ("en","zh")]
    key="ecl.25bf579ba122a8e9bc63"
    run=arrival[1]
    index=next(i for i,(f,s) in enumerate(zip(run["frames"],run["list_frames"])) if not f["held"] and key in (s.get("paragraph") or {}).get("Components",[]))
    step=run["frames"][index]["step"];panel=Image.new("RGB",(1280,420),"#202020");draw=ImageDraw.Draw(panel);sources=[]
    for i,(lang,r) in enumerate(zip(("en","zh"),arrival)):
        f=next(f for f in r["frames"] if f["step"]==step);assert not f["held"]
        path=output/("arrival-"+lang+"-"+revision)/f["File"]
        panel.paste(Image.open(path).convert("RGB"),(640*i,20));draw.text((640*i+4,2),"previous short text / "+lang,fill="white")
        sources.append(dict(path=str(path.relative_to(output)),sha256=sha(path),step=step))
    path=output/("review-existing-short-"+revision+".png");assert not path.exists();panel.save(path)
    records.append(dict(label="existing-short",sources=sources,panel=path.name,sha256=sha(path)))
    write(output/("review-images-"+revision+".json"),dict(points=records,limits="正常酒館標題、台詞及離開，另抽查舊短句；酒館三鈕未新增綁定，仍為原文。"))
    print("review points",len(records))


def evidence(root,output):
    parent=root/"workplace/probe/literal-catalog-20261024/evidence.json";previous=read(parent)
    spec=root/"docs/spec/001-early-text.md";research=root/"docs/re/005-translation-catalog.md"
    assert spec.is_file() and research.is_file()
    assert "RESOLVED-DQK11-26B4-1CD3-C61CCABA" in spec.read_text() and "#短敘事結論回填表" in spec.read_text()
    assert "26B4:1CD3" in research.read_text() and "c61ccaba966f4c04eea49304ea633c61c02566cd8ca8e93105412d50e7f239c9" in research.read_text()
    main=read(output/"gpu-check-final-r2.json");regression=read(output/"arrival-gpu-check-r2.json")
    for report in (main,regression):
        assert report["all_submitted_pixels_equal_expected"] and report["checker_sha256"]==sha(root/"tools/ui_list_live_check.py")
        assert report["reader_model_sha256"]==sha(root/"tools/ui_journal_reader_check.py")
    assert main["original_checkpoints_equal"]==5 and main["short_ecl"]["visible_keys"]
    assert read(output/"source-review.json")["source_cycles"]==4
    assert len(read(output/"visibility-review.json")["handler_stack_pairs"])==4
    assert len(read(output/"review-images-r2.json")["points"])==6
    assert len(read(output/"short-data-guards-final.json")["cases"])==3
    assert read(output/"short-data-guards-final.json")["checker_sha256"]==sha(root/"tools/ui_list_live_check.py")
    assert read(output/"short-rebuild-check.json")["generator_sha256"]==sha(root/"tools/short_ecl_inputs.py")
    fixed=read(output/"run-r4.json")
    assert sha(output/"programs-r4/ui-list-live")==fixed["program_sha256"]
    for name,h in fixed["source_files"].items():assert sha(root/name)==sha(output/"programs-r4"/Path(name).name)==h
    for name,h in fixed["inputs"].items():assert sha(output/"inputs-r1"/name)==h
    arrival=read(output/"arrival-run-r5.json")
    assert arrival["program_sha256"]==fixed["program_sha256"]
    for name,h in arrival["inputs"].items():assert sha(root/"workplace/probe"/arrival["input_path"]/name)==h
    correction=read(output/"ecl-scope-audit.json")["probe_comment_correction"]
    assert sha(output/"programs-r4/ecl-source-probe")==fixed["probe_sha256"]
    assert sha(output/"programs-r4/ecl_source_probe.go")==correction["executed_sha256"] and sha(root/"tools/ecl_source_probe.go")==correction["current_sha256"]
    assert (output/"programs-r4/ecl_source_probe.go").read_text().splitlines()[1:]==(root/"tools/ecl_source_probe.go").read_text().splitlines()[1:]
    assert sha(output/"programs-r4/ecl_source_guard_test.go")==sha(root/"tools/ecl_source_guard_test.go")
    names=list(previous["tools"])+["ecl_source_probe.go","ecl_source_ida.py","ecl_source_guard_test.go","short_ecl_inputs.py","short_ecl_evidence.py"]
    assert len(names)==len(set(names))
    snapshots=output/"tool-snapshots";assert not snapshots.exists();snapshots.mkdir()
    for name in names:shutil.copy2(root/"tools"/name,snapshots/name)
    def item(p):return dict(path=str(p.relative_to(root)),bytes=p.stat().st_size,sha256=sha(p))
    sources=[item(parent)]
    for row in previous["sources"]:
        if row["path"].startswith("workplace/translation/"):
            path=root/row["path"];assert sha(path)==row["sha256"];sources.append(item(path))
    for name in ("workplace/input/dos/drkqueen/DQK.EXE","workplace/input/dos/drkqueen/DISK3/ECL.GLB","workplace/probe/pane-render-20261022/observe-palace-journal-r1/final.state", "workplace/probe/"+arrival["state_path"]):
        sources.append(item(root/name))
    target=output/"evidence.json"
    write(target,dict(draft=True,sources=sources,artifacts=[item(p) for p in sorted(output.rglob("*")) if p.is_file() and p!=target],
        tools={n:sha(root/"tools"/n) for n in names},summary=read(output/"short-catalog-summary.json"),main=main,regression=regression,
        docker_images={**previous["docker_images"],"ida":"sha256:4ac62de83339c215bab10e455cee3a22d9c6efed9fd0d8ed0f068327b83a06ab"},
        limits="679 個新短鍵是資料接入；本輪正常新增顯示只有酒館標題。舊短句及手札 65 為稀疏 GPU 回歸，非重新完成全段細驗。受控型別變造不作正常玩家路徑。全遊戲中文化、正式入口與 HD 未完成。"))
    r=read(target);print(dict(artifacts=len(r["artifacts"]),sources=len(sources),tools=len(names)))


def audit(root,output):
    r=read(output/"evidence.json")
    for row in r["sources"]+r["artifacts"]:
        p=root/row["path"];assert p.is_file() and p.stat().st_size==row["bytes"] and sha(p)==row["sha256"],p
        assert (p.stat().st_uid,p.stat().st_gid)==(1000,1000),p
    for n,h in r["tools"].items():assert sha(root/"tools"/n)==sha(output/"tool-snapshots"/n)==h
    assert {str(p.relative_to(root)) for p in output.rglob("*") if p.is_file() and p.name!="evidence.json"}=={row["path"] for row in r["artifacts"]}
    print("audited",len(r["artifacts"]),"artifacts",len(r["sources"]),"sources",len(r["tools"]),"tools")


if __name__=="__main__":
    command=sys.argv[1]
    if command=="source-review":source_review(*map(Path,sys.argv[2:4]))
    elif command=="regression-inputs":regression_inputs(*map(Path,sys.argv[2:4]))
    elif command=="guard-recheck":guard_recheck(Path(sys.argv[2]))
    elif command=="visibility":visibility(Path(sys.argv[2]))
    elif command=="scope-audit":scope_audit(*map(Path,sys.argv[2:4]))
    elif command=="review":review(Path(sys.argv[2]))
    elif command=="evidence":evidence(*map(Path,sys.argv[2:4]))
    elif command=="audit":audit(*map(Path,sys.argv[2:4]))
    else:raise SystemExit("未知命令")
