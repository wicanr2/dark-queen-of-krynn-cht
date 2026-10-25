"""獨立重建手冊排版與操作，抽驗實際 GPU、X11、原版狀態及關閉復原。"""
import base64
import hashlib
from pathlib import Path
import sys

from PIL import Image
from journal_diagrams import read_catalog
from manual_reader_inputs import BASE, derive, lines
from original_prefix_check import image, read
from passage_runtime_inputs import sha, write
from ui_journal_reader_check import paint_reader


def model(keys, bundle, text, step=905000000):
    book = cursor = part = 0
    opened = reading = False
    expected=[]
    for key in keys:
        docs=bundle["books"][book]["documents"]
        if key == "F6":
            opened=not opened
            reading,part=False,0
        elif opened:
            if reading:
                count=(len(lines(text[docs[cursor]["body_key"]]))+12)//13
                if key == "PgDn":part=min(count-1,part+1)
                elif key == "PgUp":part=max(0,part-1)
                elif key == "Esc":reading,part=False,0
            else:
                if key in ("Left","Right"):
                    book=(book+(1 if key=="Right" else -1))%3
                    cursor=0
                elif key in ("Up","Down","PgUp","PgDn"):
                    amount={"Up":-1,"Down":1,"PgUp":-13,"PgDn":13}[key]
                    cursor=max(0,min(len(docs)-1,cursor+amount))
                elif key == "Return":reading,part=True,0
                elif key == "Esc":opened=False
        page=None
        current=bundle["books"][book]
        docs=current["documents"]
        if opened:
            page=dict(Entry=0,Heading="",Lines=[],Box=[16,16,624,256],step=step,SourceKey="")
            if reading:
                doc=docs[cursor]
                body=lines(text[doc["body_key"]])
                count=(len(body)+12)//13
                page.update(Heading=text["manual.document_heading"] % (text[current["title_key"]],doc["source_page"],text[doc["title_key"]]),
                    Lines=body[part*13:part*13+13],SourceKey=doc["body_key"],Mode="manual-body",Number=part+1,Count=count,
                    Footer=text["manual.document_hint"] % (part+1,count))
            else:
                first=cursor//13*13
                page.update(Heading=text["manual.index_heading"] % text[current["title_key"]],Mode="manual-index",
                    Lines=[text["manual.index_item"] % (text["manual.selected"] if i==cursor else " ",doc["source_page"],text[doc["title_key"]])
                           for i,doc in enumerate(docs[first:first+13],first)],Footer=text["manual.index_hint"])
        expected.append(dict(key=key,book=current["id"],cursor=cursor,part=part,reading=reading,page=page))
    assert not opened
    return expected


def check(root,out):
    assert not (out / "evidence.json").exists()
    inputs=out / "inputs-r1"
    ui=read_catalog(out / "manual-ui.zh-TW.tsv")
    text,bundle,proof=derive(root,ui)
    assert proof == read(out / "source-proof.json")
    assert bundle == read(inputs / "manual-index.json")
    needed=set(ui)|{k for b in bundle["books"] for d in b["documents"] for k in (d["title_key"],d["body_key"])}
    assert read_catalog(inputs / "manual.zh-TW.tsv") == {k:v for k,v in text.items() if k in needed}
    parent=root / "workplace/probe" / BASE
    unchanged=[]
    for p in parent.iterdir():
        if p.is_file() and p.name not in ("font-zh-TW.tsv","glyphs-16.json"):
            assert sha(p) == sha(inputs / p.name),p.name
            unchanged.append(p.name)
    glyphs=read(inputs / "glyphs-16.json")
    old=read(parent / "glyphs-16.json")
    assert all(glyphs["glyphs"][k]==v for k,v in old["glyphs"].items())
    alpha={k:base64.b64decode(v) for k,v in glyphs["glyphs"].items()}
    expected_layout=[]
    for book in bundle["books"]:
        for doc in book["documents"]:
            body=lines(text[doc["body_key"]])
            expected_layout.append(dict(id=doc["id"],lines=len(body),pages=(len(body)+12)//13,
                                        sha256=hashlib.sha256("\n".join(body).encode()).hexdigest()))
    original=root / "workplace/probe/status-menu-20261025"
    native=read(original / "city-control/receipt.json")
    fields=("regs","ram_sha256","indexed_sha256","palette","keys_consumed","file_writes","step","label")
    inherited=root / "workplace/probe/manual-reader-20261025"
    previous_text=read_catalog(inherited / "inputs-r1/manual.zh-TW.tsv")
    current_text=read_catalog(inputs / "manual.zh-TW.tsv")
    changed=[k for k in current_text if current_text[k]!=previous_text[k]]
    assert current_text.keys()==previous_text.keys()
    assert changed and all(k.startswith("table.") and k.endswith(".reader_body") for k in changed)
    assert sha(inputs / "glyphs-16.json")==sha(inherited / "inputs-r1/glyphs-16.json")
    baseline_folders={lang:(out if (out / ("baseline-"+lang)).exists() else inherited) / ("baseline-"+lang) for lang in ("en","zh")}
    baseline={lang:read(folder / "receipt.json") for lang,folder in baseline_folders.items()}
    for lang,run in baseline.items():
        previous=read(original / ("city-"+lang) / "receipt.json")
        for key in ("checkpoints","frames","list_frames","list_events","reader_events","reader_seen"):
            assert run[key] == previous[key],("unchanged parent",lang,key)
    before_images={lang:{f["step"]:f["File"] for f in run["frames"]} for lang,run in baseline.items()}
    summary={}
    for name in ("en-r2","zh-r2","x11-zh"):
        run=read(out / name / "receipt.json")
        assert run["manual_layouts"] == expected_layout
        assert run["manual_catalog_sha256"] == sha(inputs / "manual.zh-TW.tsv")
        assert run["manual_index_sha256"] == sha(inputs / "manual-index.json")
        assert run["reader_complete"] and run["final_manual"] is None
        assert not run["unimplemented"] and run["reader_seen"] == baseline["zh"]["reader_seen"] == []
        assert len(run["checkpoints"]) == len(native["checkpoints"]) == 2
        for cp,orig in zip(run["checkpoints"],native["checkpoints"]):
            assert all(cp[k]==orig[k] for k in fields),orig["label"]
            assert not cp["file_writes"]
        actual=run["manual_events"]
        if name == "x11-zh":
            keys=["F6","Return","Esc","Right","Return","Esc","Right","Return","PgDn","PgUp","Esc","F6"]
        else:
            keys=[r["key"] for r in read(out / "controls.json")["controls"]]
        assert [r["key"] for r in actual] == keys
        expected=model(keys,bundle,text)
        for a,b in zip(actual,expected):
            assert a["step"] == 905000000
            assert {k:a[k] for k in b} == b,(name,a["key"],a.get("page"))
        assert len(run["frames"]) == len(run["list_frames"])
        index,shown,restored=-1,0,0
        cache={}
        for i,(frame,meta) in enumerate(zip(run["frames"],run["list_frames"])):
            while index+1 < len(actual) and actual[index+1]["frame"] <= i:
                index+=1
            page=None if index<0 else expected[index]["page"]
            assert meta["manual"] == page,(name,i,"manual lifecycle")
            language="en" if name=="en-r2" else "zh"
            step=frame["step"]
            assert step in before_images[language]
            base=baseline_folders[language] / before_images[language][step]
            identity=base,repr(page)
            if identity not in cache:
                im=Image.open(base).convert("RGBA")
                pixels=bytearray(im.tobytes())
                if language=="zh" and page:
                    paint_reader(pixels,page,meta["palette"],alpha)
                cache[identity]=bytes(pixels)
            actual_image=Image.open(out / name / frame["File"]).convert("RGBA")
            assert hashlib.sha256(actual_image.tobytes()).hexdigest()==frame["SHA256"]
            assert actual_image.tobytes()==cache[identity],(name,i,"GPU image")
            shown+=bool(page)
            restored+=index==len(actual)-1 and page is None
        assert shown>0 and restored>0
        captures=sorted((out / name).glob("manual-[0-9]*"))
        if name=="x11-zh":
            assert len(captures)==11
            for folder in captures:
                state=read(folder / "latest.json")
                assert state["step"]==905000000 and state["reader_seen"]==[] and state["reader_stable"]
                assert image(folder / "actual-window.ppm").tobytes()==image(out / name / state["file"]).tobytes()
        summary[name]=dict(gpu_frames=len(run["frames"]),manual_frames=shown,restored_frames=restored,
                           controls=len(actual),x11_captures=len(captures))
    # 抽一個真正手札引用，確認開手冊後能恢復原有自動閱讀頁。
    old_folder=root / "workplace/probe/journal59-route-20261025"
    old_journal=read(old_folder / "main-zh-r3/receipt.json")
    stable=[(f,m) for f,m in zip(old_journal["frames"],old_journal["list_frames"]) if f["step"]==5426000000 and
            not f["held"] and m.get("reader") and not m["reader"].get("Mode")]
    assert stable and len({f["SHA256"] for f,m in stable})==1
    prior=Image.open(old_folder / "main-zh-r3" / stable[0][0]["File"]).convert("RGBA")
    journal_native=read(old_folder / "control-r2/receipt.json")["checkpoints"][:7]
    assert journal_native[-1]["indexed_sha256"]==journal_native[-2]["indexed_sha256"]
    journal={}
    for name in ("journal-en","journal-zh"):
        journal_folder=(out if (out / name).exists() else inherited) / name
        run=read(journal_folder / "receipt.json")
        assert run["reader_seen"]==[59] and run["reader_complete"] and run["final_manual"] is None
        assert run["final_auto_reader"]==run["final_reader"]==stable[0][1]["reader"]
        assert len(run["checkpoints"])==7
        for cp,orig in zip(run["checkpoints"],journal_native):
            assert all(cp[k]==orig[k] for k in fields)
            if name=="journal-en":
                frame=next(f for f in run["frames"] if f["step"]==cp["step"])
                assert image(journal_folder / frame["File"]).tobytes()==image(old_folder / "control-r2" / (cp["label"]+".png")).resize((640,400),Image.Resampling.NEAREST).tobytes()
        expected=model(["F6","Return","Esc","F6"],bundle,text,5426000000)
        events=run["manual_events"]
        assert len(events)==4 and all(e["step"]==5426000000 for e in events)
        for a,b in zip(events,expected):assert {k:a[k] for k in b}==b
        sampled=0
        if name=="journal-zh":
            for frame,meta in zip(run["frames"],run["list_frames"]):
                if frame["step"]<5426000000:continue
                px=bytearray(prior.tobytes())
                paint_reader(px,meta["manual"],meta["palette"],alpha)
                assert Image.open(journal_folder / frame["File"]).convert("RGBA").tobytes()==bytes(px)
                sampled+=1
            assert sampled>=5
        journal[name]=dict(gpu_frames=len(run["frames"]),native_checkpoints=7,controls=4,restored_auto_entry=59,sampled_images=sampled,
                           inherited=journal_folder.parent!=out)
    assert len(proof["row_groups"])==581
    for group in proof["row_groups"]:
        assert group["start"]//13==(group["start"]+group["count"]-1)//13
    write(out / "check.json",dict(documents=len(expected_layout),pages=sum(d["pages"] for d in expected_layout),
          source_text_pages=139,pending_map_pages=1,tables=50,cells=3379,literal_cells=proof["literal_cells"],table_rows_kept_together=581,
          runtime_layouts_equal_source=True,changed_table_bodies=len(changed),unchanged_files=unchanged,glyphs=len(alpha),old_glyphs_preserved=len(old["glyphs"]),
          original_state_equal=True,readers_seen_unchanged=True,baseline_equal_parent=True,runs=summary,journal_regression=journal,
          limits="全批資料及排版邊界核對；代表性目錄、正文、DOS 路徑與跨頁附表之 GPU/X11 抽驗。正式版面未定案。"))
    print(read(out / "check.json"))


if __name__ == "__main__":
    check(Path(sys.argv[1]),Path(sys.argv[2]))
