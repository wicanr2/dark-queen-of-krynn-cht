"""酒館選單的 DRAFT 資料衍生、原版核對與來源防護。"""
import json
from pathlib import Path
import shutil
import sys
import tempfile

from literal_catalog import catalog, digest, read, sha, windows
from text_catalog import write_tsv


BASE = "ecl-source-20261024/inputs-r1"
NATIVE = "bar-ui-20261024/observe-bar-r2/receipt.json"


def write(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n")


def additions(texts, trace):
    en, zh = catalog(texts/"en.tsv"), catalog(texts/"zh-TW.tsv")
    menus = [m for m in trace["menus"] if [bytes.fromhex(b["SourceHex"]).decode() for b in m["Buttons"]] == ["Drink", "Talk", "Leave"]]
    assert len(menus) == 1
    menu = menus[0]
    assert menu["Count"] == 4 and len(bytes.fromhex(menu["RawHex"])) == 128
    rows = []
    for button in menu["Buttons"]:
        source = bytes.fromhex(button["SourceHex"]).decode("ascii")
        candidates = [k for k,v in en.items() if v.casefold()==source.casefold() and k in zh]
        assert candidates and len({zh[k] for k in candidates}) == 1
        formal = min(candidates, key=lambda k:(en[k]!=source, not k.startswith("ui."), k))
        key = "field."+digest(source)[:20]
        native = lambda n:n if n<400 else (n-8000)*2
        x,y = native(button["RawX"]), native(button["RawY"])+1
        assert y == 189 and 0 <= x < x+len(source)*8 <= 320
        assert len(zh[formal])*16 <= len(source)*16
        binding = dict(Pane="menu", Group="footer", Key=key, Start=0, Length=len(source),
            Caller=dict(Seg=0xCEB,Off=0x1BE), RawX=x, RawY=y, MenuSignature=menu["Signature"],
            FormatSHA256=button["SHA256"], SHA256=button["SHA256"])
        assert binding["SHA256"] == digest(source)
        rows.append(dict(binding=binding, formal_key=formal, source=source))
    return menu, rows


def native(output):
    a,b = [read(output/(mode+"-bar-r2/receipt.json")) for mode in ("observe","control")]
    for key in ("source_commit","go_version","exe_sha256","state_sha256","request_sha256","probe_sha256","request","checkpoints"):
        assert a[key] == b[key], key
    assert a["probe_sha256"] == sha(output/"programs-r1/ui-context-probe")
    assert a["request_sha256"] == sha(output/"bar-request-r2.json")
    assert all(not a[k] for k in a if k.startswith("pending_"))
    assert len(a["checkpoints"]) == 9
    for cp in a["checkpoints"]:
        assert not cp["file_writes"] and not cp["unimplemented"]
        for suffix in (".png", ".idx"):
            assert sha(output/("observe-bar-r2/"+cp["label"]+suffix)) == sha(output/("control-bar-r2/"+cp["label"]+suffix))
    assert sha(output/"observe-bar-r2/final.state") == sha(output/"control-bar-r2/final.state")
    write(output/"native-check.json", dict(checkpoints=9, paragraphs=len(a["paragraphs"]), menus=len(a["menus"]),
        source_sha256=sha(output/"observe-bar-r2/receipt.json"), control_sha256=sha(output/"control-bar-r2/receipt.json"),
        limits="正常宮殿狀態起的進酒館、方向鍵、喝酒、交談及離開；只為原版來源，不作中文或滑鼠鍵盤實體前端驗收。"))


def generate(root, target):
    base = root/"workplace/probe"/BASE
    texts = root/"workplace/translation"
    trace = read(root/"workplace/probe"/NATIVE)
    menu, rows = additions(texts, trace)
    shutil.copytree(base, target)
    config, provenance = read(target/"inputs.json"), read(target/"provenance.json")
    en, zh, font = [catalog(target/n) for n in ("en.tsv","zh-TW.tsv","font-zh-TW.tsv")]
    formal_zh = catalog(texts/"zh-TW.tsv")
    for r in rows:
        f = r["binding"];k = f["Key"]
        assert f not in config["Fields"]
        config["Fields"].append(f)
        if k in en:assert (en[k],zh[k]) == (r["source"],formal_zh[r["formal_key"]])
        en[k], zh[k] = r["source"], formal_zh[r["formal_key"]]
        font[k] = zh[k]
    assert menu["Signature"] not in config["Menus"]
    config["Menus"][menu["Signature"]] = "bar"
    config["fine_windows"] = windows(trace)
    glyphs = read(target/"glyphs-16.json")
    assert set("".join(font.values()))-set("\r\n\t") <= set(glyphs["glyphs"])
    provenance["bar_extension"] = dict(base=BASE, base_files={p.name:sha(p) for p in base.iterdir() if p.is_file()},
        source_path=NATIVE, source_sha256=sha(root/"workplace/probe"/NATIVE), rows=rows,
        page_validation=dict(source_path=NATIVE, source_sha256=sha(root/"workplace/probe"/NATIVE)),
        formal_files={n:sha(texts/n) for n in ("en.tsv","zh-TW.tsv","glossary.tsv","catalog.json","glossary-additions.tsv")})
    for n,values in (("en.tsv",en),("zh-TW.tsv",zh),("font-zh-TW.tsv",font)):
        write_tsv(target/n,["key","text"],values.items())
    write(target/"inputs.json",config);write(target/"provenance.json",provenance)


def check_sources(inputs, config, provenance, en, zh, glyphs):
    root = inputs.parent.parent
    proof = provenance["bar_extension"]
    assert proof["base"] == BASE and proof["source_path"] == NATIVE
    base = root/BASE
    assert set(proof["base_files"]) == {p.name for p in base.iterdir() if p.is_file()}
    for n,h in proof["base_files"].items():assert Path(n).name==n and sha(base/n)==h
    assert sha(root/NATIVE) == proof["source_sha256"]
    assert proof["page_validation"] == dict(source_path=NATIVE,source_sha256=sha(root/NATIVE))
    menu, rows = additions(Path("/catalogs"), read(root/NATIVE))
    assert proof["rows"] == rows, "bar source rows"
    for n,h in proof["formal_files"].items():assert sha(Path("/catalogs")/n)==h
    old, parent = read(base/"inputs.json"), read(base/"provenance.json")
    assert {k:v for k,v in provenance.items() if k!="bar_extension"} == parent
    assert set(config) == set(old)
    assert all(config[k]==old[k] for k in config if k not in ("Fields","Menus","fine_windows")), "bar inherited config"
    assert config["Fields"] == old["Fields"]+[r["binding"] for r in rows], "bar field bindings"
    assert config["Menus"] == dict(old["Menus"], **{menu["Signature"]:"bar"}), "bar menu shape"
    assert config["fine_windows"] == windows(read(root/NATIVE)), "bar fine windows"
    old_en,old_zh = catalog(base/"en.tsv"), catalog(base/"zh-TW.tsv")
    targets = catalog(Path("/catalogs/zh-TW.tsv"))
    assert en == dict(old_en, **{r["binding"]["Key"]:r["source"] for r in rows})
    assert zh == dict(old_zh, **{r["binding"]["Key"]:targets[r["formal_key"]] for r in rows}), "bar translation"
    font = catalog(base/"font-zh-TW.tsv")
    font.update({r["binding"]["Key"]:targets[r["formal_key"]] for r in rows})
    assert catalog(inputs/"font-zh-TW.tsv") == font
    for name in set(proof["base_files"])-{"en.tsv","zh-TW.tsv","font-zh-TW.tsv","inputs.json","provenance.json"}:
        assert (inputs/name).read_bytes() == (base/name).read_bytes(), name
    assert glyphs == read(base/"glyphs-16.json")
    assert set("".join(font.values()))-set("\r\n\t") <= set(glyphs["glyphs"])
    return base,old,parent,old_en,old_zh,glyphs


def prepare(root, output):
    assert read(output/"native-check.json")["checkpoints"] == 9
    generate(root, output/"inputs-r2")


def guards(root, output):
    source = output/"inputs-r2"
    def check(path):
        return check_sources(path,read(path/"inputs.json"),read(path/"provenance.json"),catalog(path/"en.tsv"),catalog(path/"zh-TW.tsv"),read(path/"glyphs-16.json"))
    check(source)
    cases = []
    for name,reason in (("translation","bar translation"),("shape","bar menu shape"),("position","bar field bindings"),("inherited","bar field bindings")):
        with tempfile.TemporaryDirectory(dir=output,prefix="guard-") as temporary:
            target = Path(temporary);shutil.copytree(source,target,dirs_exist_ok=True)
            config = read(target/"inputs.json")
            if name == "translation":
                zh = catalog(target/"zh-TW.tsv");zh[config["Fields"][-1]["Key"]]+="x"
                write_tsv(target/"zh-TW.tsv",["key","text"],zh.items())
            else:
                if name=="shape":config["Menus"].pop(config["Fields"][-1]["MenuSignature"])
                elif name=="position":config["Fields"][-1]["RawX"]+=1
                else:config["Fields"][0]["RawX"]+=1
                write(target/"inputs.json",config)
            try:check(target)
            except AssertionError as error:assert str(error)==reason,(name,error)
            else:raise AssertionError(name)
            cases.append(dict(case=name,reason=reason))
    with tempfile.TemporaryDirectory(dir=output,prefix="rebuild-") as temporary:
        target = Path(temporary)/"inputs"
        generate(root,target)
        assert {p.name for p in source.iterdir()} == {p.name for p in target.iterdir()}
        for file in source.iterdir():assert file.read_bytes()==(target/file.name).read_bytes(),file.name
    write(output/"guards.json",dict(cases=cases,rebuilt_files=len(list(source.iterdir())),tool_sha256=sha(Path(__file__))))


def review(output):
    from PIL import Image, ImageDraw
    runs = {lang:read(output/(lang+"-r2/receipt.json")) for lang in ("en","zh")}
    r = runs["zh"]
    config = read(output/"inputs-r2/inputs.json")
    proof = read(output/"inputs-r2/provenance.json")["bar_extension"]
    bindings = [row["binding"] for row in proof["rows"]]
    required = {(f["Key"],f["RawX"],f["RawY"]) for f in bindings}
    records = []
    for cp in r["checkpoints"]:
        i = next(i for i,f in enumerate(r["frames"]) if f["step"]==cp["step"])
        frame,state = r["frames"][i],r["list_frames"][i]
        assert not frame["held"], ("stable checkpoint held",cp["label"])
        actual = {(w["Key"],w["X"],w["Y"]) for w in state["words"] or [] if w.get("Button")}
        if cp["label"]!="leave-bar-city":assert actual==required, cp["label"]
        else:
            assert len(actual)==7 and not (required & actual)
            assert config["Menus"]["993e5fca424e228be4971b0d1c5b579f45dc45da36c601b63a33ec89a0ff84e0"]=="city"
        assert state["paragraph"] and state["paragraph"]["Components"]
        records.append(dict(label=cp["label"],step=cp["step"],frame=frame["File"],sha256=frame["SHA256"],
            paragraph_components=state["paragraph"]["Components"],footer_buttons=len(actual)))
    images = []
    for label in ("bar-entry","bar-drink","bar-talk","leave-bar-city"):
        cp = next(p for p in records if p["label"]==label)
        panel = Image.new("RGB",(1280,420),"#202020")
        draw = ImageDraw.Draw(panel)
        for i,lang in enumerate(("en","zh")):
            f = next(f for f in runs[lang]["frames"] if f["step"]==cp["step"])
            assert not f["held"]
            panel.paste(Image.open(output/(lang+"-r2")/f["File"]).convert("RGB"),(i*640,20))
            draw.text((i*640+4,2),label+" / "+lang,fill="white")
        file = output/("review-"+label+".png")
        assert not file.exists()
        panel.save(file)
        images.append(dict(path=file.name,sha256=sha(file)))
    shown = []
    for binding in bindings:
        events = [e for e in r["list_events"] if e["Kind"]=="field-before-glyph" and e["detail"]["key"]==binding["Key"]
                  and e["detail"]["menu_signature"]==binding["MenuSignature"]]
        assert events and all(e["Step"]<e["first_glyph"] for e in events)
        visible = [(f,s) for f,s in zip(r["frames"],r["list_frames"]) if not f["held"] and any(
            (w["Key"],w["X"],w["Y"])==(binding["Key"],binding["RawX"],binding["RawY"]) for w in s["words"] or [])]
        assert visible
        shown.append(dict(key=binding["Key"],source_step=events[0]["Step"],first_glyph=events[0]["first_glyph"],first_visible=visible[0][0]["step"],
            visible_frames=len(visible),observed_colors=sorted({e["detail"]["word"]["Foreground"] for e in events}),
            visible_colors=sorted({w["Foreground"] for _,s in visible for w in s["words"] if w["Key"]==binding["Key"]})))
    write(output/"visibility-review.json",dict(checkpoints=records,buttons=shown,images=images,
        limits="九個穩定狀態必須實際提交，不能永遠保留前畫面冒充通過；反白事件與實際可見顏色分別計數。"))


def evidence(root, output):
    gpu = read(output/"gpu-check-r1.json")
    regression = read(output/"parent-gpu-check-final.json")
    for report in (gpu,regression):
        assert report["all_submitted_pixels_equal_expected"]
        assert report["checker_sha256"]==sha(root/"tools/ui_list_live_check.py")
    assert gpu["original_checkpoints_equal"]==9 and regression["original_checkpoints_equal"]==5
    assert len(read(output/"visibility-review.json")["checkpoints"])==9
    assert len(read(output/"guards.json")["cases"])==4
    assert read(output/"guards.json")["tool_sha256"]==sha(Path(__file__))
    parent_path = root/"workplace/probe/ecl-source-20261024/evidence.json"
    parent = read(parent_path)
    sources = [parent_path, root/"workplace/input/dos/drkqueen/DQK.EXE",
        root/"workplace/probe/pane-render-20261022/observe-palace-journal-r1/final.state"]
    for row in parent["sources"]:
        if row["path"].startswith("workplace/translation/"):
            p = root/row["path"];assert sha(p)==row["sha256"];sources.append(p)
    fixed = read(output/"run-r2.json")
    assert fixed["binary_sha256"]==sha(output/"programs-r1/ui-list-live")
    for name,h in fixed["source_files"].items():assert sha(output/"programs-r1"/name)==sha(root/"tools"/name)==h
    for name,h in fixed["input_files"].items():assert sha(output/"inputs-r2"/name)==h
    names = list(parent["tools"])+["bar_ui_inputs.py"]
    snapshot = output/"tool-snapshots";snapshot.mkdir()
    for name in names:shutil.copy2(root/"tools"/name,snapshot/name)
    def item(p):return dict(path=str(p.relative_to(root)),bytes=p.stat().st_size,sha256=sha(p))
    write(output/"evidence.json",dict(draft=True,sources=[item(p) for p in sources],
        artifacts=[item(p) for p in sorted(output.rglob("*")) if p.is_file() and p.name!="evidence.json"],
        tools={n:sha(root/"tools"/n) for n in names},gpu=gpu,regression=regression,
        docker_images={k:v for k,v in parent["docker_images"].items() if k in ("go","python")},
        limits="三鈕的正常 DRAFT 呈現與喝酒／交談／離開；正式入口、其他場景、相鄰合句、說明面板與 HD 未完成。"))


def audit(root, output):
    result = read(output/"evidence.json")
    for row in result["sources"]+result["artifacts"]:
        p=root/row["path"]
        assert p.is_file() and p.stat().st_size==row["bytes"] and sha(p)==row["sha256"],p
        assert (p.stat().st_uid,p.stat().st_gid)==(1000,1000),p
    for name,h in result["tools"].items():assert sha(root/"tools"/name)==sha(output/"tool-snapshots"/name)==h
    assert {str(p.relative_to(root)) for p in output.rglob("*") if p.is_file() and p.name!="evidence.json"}=={r["path"] for r in result["artifacts"]}
    print("audited",len(result["artifacts"]),"artifacts",len(result["sources"]),"sources",len(result["tools"]),"tools")


if __name__ == "__main__":
    command = sys.argv[1]
    if command=="native":native(Path(sys.argv[2]))
    elif command=="review":review(Path(sys.argv[2]))
    elif command in ("prepare","guards","evidence","audit"):globals()[command](*map(Path,sys.argv[2:4]))
    else:raise SystemExit("未知命令")
