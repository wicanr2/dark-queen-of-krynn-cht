"""建立冷讀研究請求及核對冷啟動前段；遊戲內畫面另走既有比較器。"""
import base64
import hashlib
import json
import sys
from pathlib import Path
from PIL import Image

def sha(data):
    return hashlib.sha256(data).hexdigest()

def load(path):
    return json.loads(path.read_text())

def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n",encoding="utf-8")

def prepare(probe, output):
    assert not output.exists()
    output.mkdir()
    # 此對存檔由既有中文營地重播真正寫出，不由測試產生假存檔。
    source = probe/"camp-live-zh-fine-20261022/scratch/SAVE"
    files = {}
    for name, size, digest in [
        ("SavGamJ.qsv",7965,"72a45079a189126c3a96d4681fac846086a6edaf26748d260d3a73fbc8905488"),
        ("VaultJ.DAT",866,"2acc13fa21f319fac65ad823d7ca52f1ed02d13ce8708431f7ce5c116d9db7ba")]:
        b=(source/name).read_bytes()
        assert len(b)==size and sha(b)==digest
        files[name]={"Bytes":size,"SHA256":digest,"ModTimeUnixNano":(source/name).stat().st_mtime_ns}
    actions=[]
    for i,key in enumerate("       pltj"):
        at=101000000+i*20000000
        actions.append(dict(At=at,End=at+19000000 if i<10 else 326000000,
                            Kind="text",Key=key,Label=f"boot-{i:02}"))
    actions.append(dict(At=327000000,End=355000000,Kind="text",Key="b",Label="verified-quiz"))
    write(output/"boot.json",dict(Actions=actions,QuizStep=355000000,Handoff=355000000,
          QuizSHA256="d7eec5b094e4265a627d2b61333d3bc7d339572431e281ac29b533e10c76ae67",SaveFiles=files))

def gameplay(output):
    native=load(output/"native-cold/receipt.json")
    actions=[]
    for i,key in enumerate("spells\n"):
        at=356000000+i*500000
        actions.append(dict(At=at,End=at+500000 if i<6 else 400000000,
                            Kind="named" if key=="\n" else "text",Key="Return" if key=="\n" else key,
                            Label=f"answer-{i:02}"))
    actions += [dict(At=at,End=end,Kind=kind,Key=key,Label=label) for at,end,kind,key,label in [
        (401000000,420000000,"text","i","loaded-inn"),
        (421000000,440000000,"named","Return","loaded-camp"),
        (441000000,460000000,"text","v","loaded-status"),
        (461000000,480000000,"text","e","return-camp"),
        (481000000,500000000,"text","e","return-city")]]
    write(output/"gameplay-request.json",dict(state_sha256=native["bridge_state_sha256"],start_steps=355000000,Actions=actions))

def fine_windows(output):
    trace=load(output/"observe-r1/receipt.json")
    intervals=[]
    limit=load(output/"gameplay-request.json")["Actions"][-1]["End"]
    for key,endkey in [("calls","return_step"),("wrappers","return_step"),
                       ("fill_events","return_instruction_step"),("paragraphs","return_step")]:
        for e in trace[key] or []:
            assert e[endkey]>e["step"]
            intervals.append([max(355000000,e["step"]-2000),min(limit,e[endkey]+2000)])
    merged=[]
    for start,end in sorted(intervals):
        if merged and start<=merged[-1][1]:merged[-1][1]=max(merged[-1][1],end)
        else:merged.append([start,end])
    assert merged
    assert not (output/"native-fine-windows.json").exists()
    write(output/"native-fine-windows.json",merged)
    print(json.dumps(dict(windows=len(merged),instructions=sum(b-a for a,b in merged))))

def guards_prepare(probe, output):
    target=output/"runtime-guards"
    assert not target.exists()
    target.mkdir()
    import copy
    original=load(output/"boot.json")
    bad=copy.deepcopy(original)
    bad["SaveFiles"]["SavGamJ.qsv"]["SHA256"]="0"*64
    write(target/"bad-source.json",bad)
    bad=copy.deepcopy(original);bad["QuizSHA256"]="0"*64
    write(target/"bad-quiz.json",bad)
    bad=copy.deepcopy(original);bad["SaveFiles"]["VaultJ.DAT"]["ModTimeUnixNano"]+=2000000000
    write(target/"bad-time.json",bad)
    role=target/"role16";role.mkdir()
    (role/"zh-TW.tsv").write_bytes((probe/"interactive-menu-inputs-20261022/zh-TW.tsv").read_bytes())
    (role/"glyphs-20.json").write_bytes((probe/"services-trade-20261023/inputs-r2/glyphs-16.json").read_bytes())

def reuse(probe, output, previous):
    import shutil
    assert Path(previous).name==previous
    source=probe/previous
    assert (source/"boot.json").read_bytes()==(output/"boot.json").read_bytes()
    receipt=load(source/"native-cold/receipt.json")
    assert receipt["source_commit"]=="f79eab6db8c64a524a06535e53e5d32b0bbcf7c8"
    assert receipt["request_sha256"]==sha((output/"boot.json").read_bytes())
    assert not receipt["unimplemented"] and not receipt["snapshot_loaded"]
    copied=[]
    for name in ["native-cold","observe-r1","control-r1","legacy-observe-r1","legacy-control-r1"]:
        if not (output/name).exists():shutil.copytree(source/name,output/name)
        else:assert sorted(str(p.relative_to(output/name)) for p in (output/name).rglob("*") if p.is_file())==sorted(str(p.relative_to(source/name)) for p in (source/name).rglob("*") if p.is_file())
        for file in sorted((source/name).rglob("*")):
            if file.is_file():
                destination=output/file.relative_to(source)
                digest=sha(file.read_bytes());assert sha(destination.read_bytes())==digest
                copied.append(dict(source=str(file.relative_to(probe)),destination=str(destination.relative_to(output)),sha256=digest))
    for name in ["gameplay-request.json","native-fine-windows.json","original-check.json","legacy-original-check.json"]:
        assert not (output/name).exists()
        shutil.copyfile(source/name,output/name)
        copied.append(dict(source=str((source/name).relative_to(probe)),destination=name,sha256=sha((source/name).read_bytes())))
    write(output/"native-reuse.json",dict(origin=previous,files=copied,limits="逐位元組保留原版 dosgolem 收據；本輪呈現程序另從 MZ 重跑，不從這些快照啟動。"))
    print(json.dumps(dict(reused_original_artifacts=len(copied))))

def check(probe, output, en_name, zh_name, result_name="cold-check.json"):
    assert not (output/result_name).exists()
    native=load(output/"native-cold/receipt.json")
    req=load(output/"boot.json")
    roles=probe/"interactive-menu-inputs-20261022"
    from camp_live_inputs import catalog
    translations=catalog(roles/"zh-TW.tsv")
    glyphs=load(roles/"glyphs-20.json")
    assert glyphs["size"]==20 and glyphs["height"]==24
    alpha={k:base64.b64decode(v) for k,v in glyphs["glyphs"].items()}
    a,b=[load(output/n/"receipt.json") for n in (en_name,zh_name)]
    fields=("label","step","regs","ram_sha256","indexed_sha256","palette","keys_consumed","file_writes")
    for x in (a,b):
        assert x["cold_boot"] and not x["snapshot_loaded"] and "initial_state_sha256" not in x
        assert x["cold_request_sha256"]==native["request_sha256"]==sha((output/"boot.json").read_bytes())
        assert x["bridge_state_sha256"]==native["bridge_state_sha256"]==sha((output/"native-cold/handoff.state").read_bytes())
        assert x["cold_role_catalog_sha256"]==sha((roles/"zh-TW.tsv").read_bytes())
        assert x["cold_role_glyphs_sha256"]==sha((roles/"glyphs-20.json").read_bytes())
        assert len(x["cold_checkpoints"])==len(native["checkpoints"])==len(req["Actions"])
        for p,q in zip(x["cold_checkpoints"],native["checkpoints"]):
            assert all(p[f]==q[f] for f in fields),p["label"]
            assert not q["unimplemented"]
        assert not x["unimplemented"]
        for name,spec in req["SaveFiles"].items():
            for d in [probe/"camp-live-zh-fine-20261022",output/"native-cold",output/en_name,output/zh_name]:
                raw=(d/"scratch/SAVE"/name).read_bytes()
                assert len(raw)==spec["Bytes"] and sha(raw)==spec["SHA256"]
                assert (d/"scratch/SAVE"/name).stat().st_mtime_ns==spec["ModTimeUnixNano"]
    assert a["cold_events"]==b["cold_events"] and a["cold_boundaries"]==b["cold_boundaries"]
    assert len(a["cold_frames"])==len(b["cold_frames"])
    events=b["cold_events"]
    assert events, "冷讀缺少角色管理中文觀測器"
    active={};last_count=0; previous=None; changed=0; held=0
    boundary_index=0;bounds=b["cold_boundaries"]
    palettes={cp["step"]:cp["palette"] for cp in native["checkpoints"]}
    # 同一模式各選單的 EGA 色盤一致；僅在原版設定色盤後有中文事件。
    palette=palettes[326000000]
    if a.get("cold_ui") and len(load(Path(a["cold_ui"]["input_root"])/"bindings.json")["Bindings"])==15:
        assert all(cp["palette"][:16]==palette[:16] for cp in native["checkpoints"] if cp["step"]>=240000000)
    ui=None;ui_index=0;ui_words=[];ui_pending=False;ui_count=0
    if a.get("cold_ui") or b.get("cold_ui"):
        assert a.get("cold_ui") and b.get("cold_ui")
        from load_prompt_check import model,paint,pending_at
        ui=model(probe,a,b)
    for f,g in zip(a["cold_frames"],b["cold_frames"]):
        assert (f["step"],f["events"],f["held"],f["active"])==(g["step"],g["events"],g["held"],g["active"])
        step=g["step"]
        if ui is not None:
            count=g.get("cold_ui_events",0)
            assert ui_index<=count<=len(ui["timeline"])
            assert count==0 or ui["timeline"][count-1][0]<=step
            assert count==len(ui["timeline"]) or ui["timeline"][count][0]>=step
            if count:_,ui_words,ui_pending,ui_count=ui["timeline"][count-1]
            ui_index=count
            for frame in (f,g):
                assert (frame.get("cold_ui_words") or [])==ui_words,("cold UI words",step)
                assert frame.get("cold_ui_events",0)==ui_count
                expected_pending=pending_at(ui,frame,count,ui_words,ui_pending)
                assert frame.get("cold_ui_pending",False)==expected_pending,("cold pending",step)
                if expected_pending:assert frame["held"]
        # 依真實時間交錯清除與新標籤；相同 step 的邊界均早於 Draw。
        merged=[(e["step"],0,e) for e in bounds[boundary_index:] if e["step"]<=step]
        merged += [(e["step"],1,e) for e in events[last_count:g["events"]]]
        for _,kind,e in sorted(merged,key=lambda v:(v[0],v[1])):
            if kind==0:
                if e["kind"] in ("transition-render-entry","begin-adventure-native-hud"): active={}
                boundary_index+=1
            else: active[(e["X"],e["Y"])]=e
        last_count=g["events"]
        pixels=[]
        for n,frame in [(en_name,f),(zh_name,g)]:
            assert Path(frame["File"]).name==frame["File"]
            with Image.open(output/n/frame["File"]) as im:
                assert im.size==(640,400);raw=im.convert("RGBA").tobytes()
            assert sha(raw)==frame["SHA256"]
            pixels.append(raw)
        assert len(active)==g["active"]
        if g["held"]:
            assert previous is not None and pixels[1]==previous;held+=1
        else:
            expected=bytearray(pixels[0])
            for e in sorted(active.values(),key=lambda e:(e["Y"],e["X"])):
                assert translations[e["Key"]]==e["Text"] and sha(e["Source"].encode())==e["Key"]
                x,y,width=e["X"]*2,e["Y"]*2,len(e["Source"])*16
                bg,fg=palette[(e["Color"]>>4)&15],palette[e["Color"]&15]
                for yy in range(y,y+16):
                    expected[(yy*640+x)*4:(yy*640+x+width)*4]=bytes([*bg,255])*width
                for i,ch in enumerate(e["Text"]):
                    mask=alpha[ch];assert len(mask)==480
                    for yy in range(24):
                        for xx in range(20):
                            v=mask[yy*20+xx]
                            if not v:continue
                            at=((y-2+yy)*640+x+i*20+xx)*4
                            for c in range(3):expected[at+c]=(fg[c]*v+expected[at+c]*(255-v)+127)//255
            if ui is not None:
                paint(expected,ui_words,palette,ui)
                for word in ui_words:ui["visible"][word["Key"]]+=1
            assert bytes(expected)==pixels[1],("cold pixels",step)
            changed+=pixels[0]!=pixels[1]
        previous=pixels[1]
    assert changed>0 and held>0 and not active
    if ui is not None:assert all(ui["visible"].values()),ui["visible"]
    if ui is not None:
        for receipt in (a,b):
            for lo,hi in ui["fine_windows"]:
                gaps=[right["step"]-left["step"] for left,right in zip(receipt["cold_frames"],receipt["cold_frames"][1:]) if right["step"]>lo and left["step"]<hi]
                assert gaps and max(gaps)<=2000,("cold caption observation gap",lo,hi,max(gaps) if gaps else None)
    windows=load(output/"native-fine-windows.json")
    trace=load(output/"observe-r1/receipt.json")
    for key,endkey in [("calls","return_step"),("wrappers","return_step"),
                       ("fill_events","return_instruction_step"),("paragraphs","return_step")]:
        for e in trace[key] or []:
            assert any(lo<=e["step"]<e[endkey]<=hi for lo,hi in windows)
    for receipt in (a,b):
        assert receipt["cold_fine_windows_sha256"]==sha((output/"native-fine-windows.json").read_bytes())
        for lo,hi in windows:
            for left,right in zip(receipt["frames"],receipt["frames"][1:]):
                if right["step"]>lo and left["step"]<hi:
                    assert right["step"]-left["step"]<=2000
    assert native["cold_boot"] and not native["snapshot_loaded"]
    assert native["source_commit"]=="f79eab6db8c64a524a06535e53e5d32b0bbcf7c8"
    assert native["go_version"]=="go1.24.13" and native["exe_sha256"]=="3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58"
    result=dict(cold_boot=True,gui_snapshot_loaded=False,original_checkpoints_equal=len(native["checkpoints"]),
                gpu_frames_verified=len(b["cold_frames"]),translated_frames=changed,held_frames=held,
                role_font_size=20,gameplay_font_size=16,save_files=req["SaveFiles"],
                native_paint_windows=len(windows),maximum_paint_observation_step_gap=2000,
                runs=[en_name,zh_name],receipt_sha256=[sha((output/n/"receipt.json").read_bytes()) for n in (en_name,zh_name)],
                checker_sha256=sha(Path(__file__).read_bytes()),
                limits="DRAFT role labels and post-load gameplay only; original load-source, slot and quiz prompts remain; no all-game/interactive keyboard claim")
    if ui is not None:
        result["cold_prompt_visible_frames"]=ui["visible"];result["cold_prompt_events"]=ui["events"]
        result["cold_prompt_model_sha256"]=sha(Path(__file__).with_name("load_prompt_check.py").read_bytes())
        result["limits"]="DRAFT role labels plus six load captions; original quiz and other unbound text remain; no all-game/interactive keyboard claim"
        if len(ui["keys"])==15:
            result["cold_caption_paint_windows"]=len(ui["fine_windows"])
            result["cold_page_sync_verified"]=ui["page_sync"]
            result["limits"]="DRAFT opening, load, name and quiz captions; English quiz heading, numbers and answer remain original; no all-game/interactive keyboard claim"
    write(output/result_name,result)
    print(json.dumps(result,ensure_ascii=False))

def negative(probe, output, en_name, zh_name):
    from unittest.mock import patch
    target=output/"checker-negatives"
    assert not target.exists();target.mkdir()
    receipt_path=output/zh_name/"receipt.json"
    original=load(receipt_path)
    en=load(output/en_name/"receipt.json")
    pair=next((f,g) for f,g in zip(en["cold_frames"],original["cold_frames"]) if not g["held"] and g["active"] and f["SHA256"]!=g["SHA256"])
    f,g=pair
    with Image.open(output/en_name/f["File"]) as im:control=im.convert("RGBA").tobytes()
    with Image.open(output/zh_name/g["File"]) as im:raw=bytearray(im.convert("RGBA").tobytes())
    at=next(i for i in range(len(raw)) if i%4!=3 and raw[i]!=control[i]);raw[at]^=1
    Image.frombytes("RGBA",(640,400),bytes(raw)).save(target/"changed-role-pixel.png")
    read_impl,open_impl=load,Image.open
    cached={}
    results=[]
    for name in ["guest-ram","role-font","snapshot-claim","gpu-pixel-with-valid-sha"]:
        # 兩份完整收據各約 193 MB；只複製本案例變動的欄位，不再複製全部遊戲畫格。
        changed=original.copy()
        if name=="guest-ram":
            changed["cold_checkpoints"]=[cp.copy() for cp in original["cold_checkpoints"]]
            changed["cold_checkpoints"][-1]["ram_sha256"]="0"*64
        elif name=="snapshot-claim":changed["initial_state_sha256"]=changed["bridge_state_sha256"]
        elif name=="gpu-pixel-with-valid-sha":
            changed["cold_frames"]=[frame.copy() for frame in original["cold_frames"]]
            for frame in changed["cold_frames"]:
                if frame["File"]==g["File"]:frame["SHA256"]=sha(raw)
        def altered_load(path):
            if path==receipt_path:return changed
            if path==output/en_name/"receipt.json":return en
            if path not in cached:cached[path]=read_impl(path)
            value=cached[path]
            if name=="role-font" and path==probe/"interactive-menu-inputs-20261022/glyphs-20.json":
                value=value.copy();value["size"]=16
            return value
        def altered_open(path,*args,**kwargs):
            if name=="gpu-pixel-with-valid-sha" and path==output/zh_name/g["File"]:
                return open_impl(target/"changed-role-pixel.png",*args,**kwargs)
            return open_impl(path,*args,**kwargs)
        with patch(__name__+".load",altered_load),patch.object(Image,"open",altered_open):
            try:check(probe,output,en_name,zh_name,"negative-unexpected.json")
            except AssertionError as error:
                if name=="gpu-pixel-with-valid-sha":assert "cold pixels" in str(error),str(error)
                results.append(dict(name=name,rejected=True,reason=str(error)))
            else:raise AssertionError("應拒絕卻通過："+name)
    write(target/"results.json",dict(cases=results,checker_sha256=sha(Path(__file__).read_bytes())))
    print(json.dumps(results,ensure_ascii=False))

def evidence(root, output):
    import gzip
    import shutil
    probe=root/"workplace/probe"
    cold,game,legacy,original=[load(output/n) for n in ["cold-check.json","gameplay-check.json","legacy-check.json","original-check.json"]]
    assert cold["original_checkpoints_equal"]==12 and game["original_checkpoints_equal"]==12
    assert legacy["original_checkpoints_equal"]==16 and original["checkpoints_equal"]==12
    assert len((output/"runtime-guards/results.tsv").read_text().splitlines())==5
    assert len(load(output/"checker-negatives/results.json")["cases"])==4
    assert cold["checker_sha256"]==sha(Path(__file__).read_bytes())
    assert game["checker_sha256"]==legacy["checker_sha256"]==sha((root/"tools/ui_list_live_check.py").read_bytes())
    for name in ["en-r1-memory-events.txt","zh-r1-memory-events.txt","runtime-guards/memory-events.txt"]:
        events=dict(line.split() for line in (output/name).read_text().splitlines())
        assert events["oom"]==events["oom_kill"]=="0"
    snapshot=output/"tool-snapshots"
    assert not snapshot.exists()
    snapshot.mkdir()
    tool_names=["cold-load.sh","cold_load.py","cold_load_probe.go","early_text_live.go","ui_list_live.go","ui_hud_integer.go",
                "ui_list_live_check.py","ui_list_inputs.py","ui_list_paragraphs.go","ui_journal_reader.go",
                "ui_journal_illustrations.go","ui_menu_source.go","oracle_video_observer.go","ui-list-live.sh",
                "ui_context_probe.go","ui_context_check.py","ui-context.sh","camp_live_inputs.py",
                "ui_journal_reader_check.py","ui_journal_illustrations_check.py"]
    tools={}
    for name in tool_names:
        source=root/"tools"/name
        shutil.copyfile(source,snapshot/name)
        tools[name]=sha(source.read_bytes())
    for name in ["ui-list-live","cold-load-probe","ui-context-probe"]:
        shutil.copyfile(probe/name,snapshot/name)
    # 舊失敗保留，逐位元組定位到 DOS 檔案時間，不能把整份機器狀態當作等價略過。
    old=probe/"cold-load-20261023"
    paths=[old/"native-cold/handoff.state",old/"en-r1/cold-handoff.state"]
    raw=[gzip.decompress(p.read_bytes()) for p in paths]
    differences=[i for i,(x,y) in enumerate(zip(*raw)) if x!=y]
    assert len(raw[0])==len(raw[1]) and differences==[267385]
    from datetime import datetime
    times=[]
    for directory in [old/"native-cold",old/"en-r1"]:
        file=directory/"scratch/SAVE/VaultJ.DAT"
        t=datetime.fromtimestamp(file.stat().st_mtime)
        word=t.hour<<11|t.minute<<5|t.second//2
        times.append(dict(path=str(file.relative_to(probe)),mtime_ns=file.stat().st_mtime_ns,dos_time_word=word))
    assert [int.from_bytes(x[267385:267387],"little") for x in raw]==[x["dos_time_word"] for x in times]
    write(output/"file-time-diagnostic.json",dict(old_snapshots=[dict(path=str(p.relative_to(probe)),sha256=sha(p.read_bytes())) for p in paths],
          address_space="gzip 解壓後的機器／DOS 串接序列化檔案偏移；不是遊戲線性位址",difference_offset=267385,times=times,
          contract="dosgolem f79eab6 internal/dos/find.go dosDateTime：檔案修改時間填入 DOS 查找結果；來源時間須隨存檔一起複製"))
    def fingerprint(path):
        h=hashlib.sha256()
        with path.open("rb") as stream:
            while data:=stream.read(1<<20):h.update(data)
        return dict(path=str(path.relative_to(root)),bytes=path.stat().st_size,sha256=h.hexdigest())
    sources=[root/"workplace/input/dos/drkqueen/DQK.EXE"]
    sources += [root/"workplace/translation"/n for n in ["zh-TW.tsv","en.tsv","glossary.tsv","catalog.json","glossary-additions.tsv"]]
    sources += [probe/"interactive-menu-inputs-20261022"/n for n in ["zh-TW.tsv","glyphs-20.json"]]
    sources += [probe/"services-trade-20261023/inputs-r2"/n for n in ["inputs.json","en.tsv","zh-TW.tsv","glyphs-16.json","provenance.json","reader.zh-TW.tsv","illustrations.json"]]
    sources += [probe/"camp-live-zh-fine-20261022"/n for n in ["receipt.json","camp-comparison.json","scratch/SAVE/SavGamJ.qsv","scratch/SAVE/VaultJ.DAT"]]
    sources += [probe/"services-trade-20261023/evidence-r2.json"]
    artifacts=[]
    for name in ["native-cold","observe-r1","control-r1","en-r1","zh-r1","legacy-en-r1","legacy-zh-r1","legacy-observe-r1","legacy-control-r1","runtime-guards","checker-negatives","checker-negatives-before-memory","tool-snapshots"]:
        artifacts += [fingerprint(p) for p in sorted((output/name).rglob("*")) if p.is_file()]
    artifacts += [fingerprint(p) for p in sorted(output.iterdir()) if p.is_file() and p.suffix in (".json",".txt",".log") and p.name!="evidence.json"]
    result=dict(draft=True,scope="中文 J 存檔的連續 MZ 冷讀；角色管理 20px、遊戲內 16px 原型，未完成全部讀檔提示及正式入口",
        source_commit="f79eab6db8c64a524a06535e53e5d32b0bbcf7c8",tools=tools,sources=[fingerprint(p) for p in sources],artifacts=artifacts,
        docker_images=dict(go="sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581",python="sha256:44d0742ca1061bcd453440cdce925afa31c5324e115fca1334da0e364f0e2c48"),
        cold=cold,gameplay=game,legacy=legacy,original=original,
        failed_attempts=["cold-load-20261023：錯估讀回後位置，且存檔複製遺失來源修改時間；不作成功證據",
                         "cold-load-20261023-r2/zh-r1：字模 map 共用，20px 載入污染 16px；不作成功證據",
                         "cold-load-20261023-r2/en-r2、zh-r2：缺少角色中文觀測器與閱讀資料接入，比較器拒絕；不作成功證據",
                         "cold-load-20261023-r2/en-r3、zh-r3：已確認相同接線缺口而停止；不作成功證據"],
        rights="原版、存檔、完整譯文、字模、畫格與工具二進位僅留本機 workplace，不加入 Git")
    assert not (output/"evidence.json").exists()
    write(output/"evidence.json",result)
    print(json.dumps(dict(artifacts=len(artifacts),tools=len(tools))))

if __name__=="__main__":
    mode=sys.argv[1]
    if mode=="prepare":prepare(*map(Path,sys.argv[2:4]))
    elif mode=="gameplay":gameplay(Path(sys.argv[2]))
    elif mode=="fine":fine_windows(Path(sys.argv[2]))
    elif mode=="guards-prepare":guards_prepare(*map(Path,sys.argv[2:4]))
    elif mode=="reuse":reuse(Path(sys.argv[2]),Path(sys.argv[3]),sys.argv[4])
    elif mode=="check":check(Path(sys.argv[2]),Path(sys.argv[3]),*sys.argv[4:6])
    elif mode=="negative":negative(Path(sys.argv[2]),Path(sys.argv[3]),*sys.argv[4:6])
    elif mode=="evidence":evidence(*map(Path,sys.argv[2:4]))
    else:raise SystemExit("未知命令")
