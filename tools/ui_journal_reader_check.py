"""以原版段落與校讀 TSV 獨立檢查閱讀、分頁與查閱，不呼叫 Go 排版。"""
def legacy_reader_model(inputs, config, native_paragraphs, accepted, runs):
    from ui_list_inputs import catalog, sha
    path = inputs / "reader.zh-TW.tsv"
    if not path.exists():
        assert all("reader_events" not in run and "reader_catalog_sha256" not in run
                   and all("reader" not in f for f in run["list_frames"]) for run in runs)
        return None
    texts = catalog(path)
    assert all(isinstance(f.get("JournalEntry"),int) and 1 <= f["JournalEntry"] <= 99
               for f in config.get("Paragraphs",[]) if f["Key"].startswith("message.")), "引用缺少手札編號"
    assert texts["reader.heading"].count("%s") == 2
    pages = {}
    for key, title in texts.items():
        if not key.endswith(".title"):
            continue
        entry = int(key.split(".")[1])
        body = texts[f"journal.{entry}.body"]
        lines = []
        for paragraph in body.split(r"\n"):
            if not paragraph:
                lines.append("")
                continue
            at = 0
            while at < len(paragraph):
                ends = [end for end in range(at+1, min(at+38, len(paragraph))+1)
                        if end == len(paragraph) or
                        (paragraph[end] not in "，。！？、；：」』）》】" and paragraph[end-1] not in "「『（《【")]
                assert ends, "手札無合法分界"
                end = max(ends)
                lines.append(paragraph[at:end])
                at = end
        assert 0 < len(lines) <= 13, "手札超頁"
        heading = texts["reader.heading"] % (entry, title)
        assert len(heading) <= 37
        pages[entry] = {"Entry":entry, "Heading":heading, "Lines":lines, "Box":[16,16,624,256]}
    assert pages and len(texts) == 1+len(pages)*2
    accepted_by_step = {e["Step"]:e for e in accepted}
    events, history, page = [], [], None
    for p in native_paragraphs:
        step = p["step"]
        if page is not None:
            events.append({"step":step,"action":"close","entry":page["Entry"],"reason":"next paragraph"})
            page = None
        event = accepted_by_step.get(step)
        if event:
            bindings = [f for f in config["Paragraphs"] if f["Key"] == event["detail"]["page"]["Key"]
                        and f["Caller"]==p["caller"] and f["NativeBox"]==p["native_box"]
                        and [f[k] for k in ("Foreground","Background","Clear")]==[p[k] for k in ("foreground","background","clear")]
                        and f["SHA256"]==sha(p["source"]["text"].encode())]
            assert len(bindings) == 1
            binding = bindings[0]
            entry = binding.get("JournalEntry",0)
            if entry:
                if entry in pages:
                    page = {**pages[entry],"step":step,"SourceKey":binding["Key"]}
                    events.append({"step":step,"action":"open","page":page})
                else:
                    events.append({"step":step,"action":"unavailable","entry":entry,"source_key":binding["Key"]})
        history.append((step,page))
    for run in runs:
        assert run["reader_catalog_sha256"] == sha(path.read_bytes())
        assert (run["reader_events"] or []) == events, "手札開關與原版段落不符"
        assert run["final_reader"] == page
        index = -1
        for frame in run["list_frames"]:
            while index+1 < len(history) and history[index+1][0] <= frame["step"]:
                index += 1
            assert "reader" in frame and frame["reader"] == (history[index][1] if index >= 0 else None), ("手札生命週期",frame["step"])
    return {"events":events, "entries":len(pages), "catalog_sha256":sha(path.read_bytes())}


def reader_model(inputs, config, native_paragraphs, accepted, runs):
    import json
    from ui_journal_illustrations_check import illustrations, move, IMAGE_KEYS
    from ui_list_inputs import catalog, sha
    path = inputs / "reader.zh-TW.tsv"
    if not path.exists() or "reader.page" not in catalog(path):
        return legacy_reader_model(inputs,config,native_paragraphs,accepted,runs)
    text = catalog(path)
    ui = {"reader.heading","reader.page","reader.empty","reader.browse_hint"}
    images = illustrations(inputs)
    if images: ui.add("reader.image_hint")
    assert ui <= text.keys()
    entries = {}
    for key in text:
        if not key.endswith(".title"):
            continue
        entry = int(key.split(".")[1])
        if entry in images:
            assert f"journal.{entry}.body" not in text
            entries[entry]=(text["reader.heading"] % (entry,text[key]),[[]])
            continue
        lines = []
        for paragraph in text[f"journal.{entry}.body"].split(r"\n"):
            if not paragraph:
                lines.append("")
            while paragraph:
                end = max(i for i in range(1,min(38,len(paragraph))+1) if i==len(paragraph) or
                          (paragraph[i] not in "，。！？、；：」』）》】" and paragraph[i-1] not in "「『（《【"))
                lines.append(paragraph[:end]); paragraph=paragraph[end:]
        assert 0 < len(lines) <= 39
        heading = text["reader.heading"] % (entry,text[key])
        assert len(heading) <= 37
        entries[entry] = (heading,[lines[i:i+13] for i in range(0,len(lines),13)])
    assert entries and len(text)==len(ui)+len(entries)*2-len(images)
    def page_for(entry,index,mode,source,step):
        heading,pages=entries[entry]
        assert 0 <= index < len(pages)
        p={"Entry":entry,"Heading":heading,"Lines":pages[index],"Box":[16,16,624,256],"step":step,"SourceKey":source}
        footer=""
        if len(pages)>1:
            p.update(Number=index+1,Count=len(pages));footer=text["reader.page"] % (index+1,len(pages))
        if mode in ("browse","probe"):
            footer=(footer+" " if footer else "")+text["reader.browse_hint"]
        if entry in images:
            p["Image"]={"zoom":0,"x":0,"y":0};footer=text["reader.image_hint"]
        if footer:
            assert len(footer)<=38;p["Footer"]=footer
        if mode:p["Mode"]=mode
        return p
    accepted_by_step={e["Step"]:e for e in accepted}
    controls_path=inputs/"reader-controls.json"
    controls=json.loads(controls_path.read_text())["controls"] if controls_path.exists() else []
    summaries=[]
    native_events_all=None
    for run in runs:
        paragraph_order={e["Step"]:i for i,e in enumerate(run.get("list_events") or [])
                         if e["Kind"] in ("paragraph-before-glyph","unknown-paragraph-original")}
        if images: assert run["reader_illustrations_sha256"]==sha((inputs/"illustrations.json").read_bytes())
        assert run["reader_catalog_sha256"]==sha(path.read_bytes()) and run["reader_complete"]
        assert run["reader_controls_sha256"]==(sha(controls_path.read_bytes()) if controls_path.exists() else "")
        ui_events=run["reader_ui_events"] or []
        by_frame={}
        for e in ui_events:
            assert e["source"] in ("script","probe","keyboard") and e["key"] in {"F5","Esc","PgUp","PgDn","Left","Right","Gallery","Preview"}|IMAGE_KEYS
            assert 0 <= e["frame"] < len(run["list_frames"])
            by_frame.setdefault(e["frame"],[]).append(e)
        scripted=[e for e in ui_events if e["source"]!="keyboard"]
        assert len(scripted)==len(controls)
        for actual,expected in zip(scripted,controls):
            assert actual["step"]==expected["at"] and actual["key"]==expected["key"] and actual.get("entry",0)==expected.get("entry",0)
            assert actual["source"]==("probe" if actual["key"] in ("Gallery","Preview") else "script")
            if actual["source"]=="probe":assert run["reader_probe"]
        native_events,expected_gallery=[],[]
        seen,last={},0
        visible,auto,saved=None,None,None
        index,saved_index,p_index=0,0,0
        mode=""
        gallery=None
        for frame_index,frame in enumerate(run["list_frames"]):
            step=frame["step"]
            if mode or gallery is not None:
                assert frame_index > 0 and step==run["list_frames"][frame_index-1]["step"], "查閱期間原版步數改變"
            while p_index<len(native_paragraphs) and native_paragraphs[p_index]["step"]<=step:
                pending=native_paragraphs[p_index]["step"]
                # Run 可恰好停在呼叫前。同一步數的畫格以已驗證的事件序號判斷邊界。
                if pending==step and pending in paragraph_order and paragraph_order[pending]>=frame.get("list_event_count",len(run.get("list_events") or [])):
                    break
                assert mode=="" and gallery is None, "原版在查閱期間前進"
                p=native_paragraphs[p_index];p_index+=1
                if auto is not None:
                    native_events.append({"step":p["step"],"action":"close","entry":auto["Entry"],"reason":"next paragraph"})
                    auto,visible,index=None,None,0
                event=accepted_by_step.get(p["step"])
                if event:
                    bindings=[f for f in config["Paragraphs"] if f["Key"]==event["detail"]["page"]["Key"]
                              and f["Caller"]==p["caller"] and f["NativeBox"]==p["native_box"]
                              and [f[k] for k in ("Foreground","Background","Clear")]==[p[k] for k in ("foreground","background","clear")]
                              and f["SHA256"]==sha(p["source"]["text"].encode())]
                    assert len(bindings)==1
                    binding=bindings[0];entry=binding.get("JournalEntry",0)
                    if entry:
                        if entry in entries:
                            auto=page_for(entry,0,"",binding["Key"],p["step"])
                            visible,index=auto,0;seen[entry]=binding["Key"];last=entry
                            native_events.append({"step":p["step"],"action":"open","page":auto})
                        else:native_events.append({"step":p["step"],"action":"unavailable","entry":entry,"source_key":binding["Key"]})
            if gallery is not None:
                assert not by_frame.get(frame_index) and step==gallery["step"]
                if gallery["at"]<len(gallery["pages"]):
                    visible=gallery["pages"][gallery["at"]];gallery["at"]+=1
                    expected_gallery.append({"step":step,"frame":frame_index,"entry":visible["Entry"],"page":visible.get("Number",1)})
                else:
                    visible,index=saved,saved_index;saved=None;gallery=None
            for e in by_frame.get(frame_index,[]):
                if e.get("ignored"):
                    assert e["source"]=="keyboard" and e["ignored"]=="unstable" and e["step"]<=step
                    continue
                assert e["step"]==step
                key=e["key"]
                if key in IMAGE_KEYS:
                    assert visible and visible.get("Image")
                    visible={**visible,"Image":move(images[visible["Entry"]],visible["Image"],key)}
                elif key=="Gallery":
                    assert mode=="" and gallery is None
                    saved,saved_index=visible,index
                    gallery={"step":step,"at":0,"pages":[page_for(i,j,"gallery","",step) for i in sorted(entries) for j in range(len(entries[i][1]))]}
                elif key=="Preview":
                    assert mode=="" and run["reader_probe"]
                    saved,saved_index=visible,index;mode,index="probe",0
                    visible=page_for(e["entry"],0,mode,"",step)
                elif key in ("F5","Esc"):
                    if mode=="probe":visible,index,mode=saved,saved_index,"";saved=None
                    elif mode=="browse":visible,index,mode=None,0,""
                    elif key=="F5":
                        mode,index="browse",0
                        visible=page_for(last,0,mode,seen[last],step) if last else {
                            "Entry":0,"Heading":text["reader.empty"],"Lines":[],"Box":[16,16,624,256],"step":step,"SourceKey":"", "Footer":text["reader.browse_hint"],"Mode":mode}
                elif key in ("PgUp","PgDn") and visible and visible["Entry"]:
                    at=index+(1 if key=="PgDn" else -1)
                    if 0<=at<len(entries[visible["Entry"]][1]):
                        index=at;visible=page_for(visible["Entry"],index,mode,visible["SourceKey"],step)
                elif key in ("Left","Right") and mode=="browse" and seen:
                    ids=sorted(seen);at=(ids.index(visible["Entry"])+(1 if key=="Right" else -1))%len(ids)
                    index=0;visible=page_for(ids[at],0,mode,seen[ids[at]],step)
                assert e["page"]==visible, ("查閱控制結果",e)
            assert frame["reader"]==visible, ("查閱畫格",frame_index,step)
        assert p_index==len(native_paragraphs) and mode=="" and gallery is None
        assert (run["reader_events"] or [])==native_events and run["final_auto_reader"]==auto
        assert (run["reader_gallery_frames"] or [])==expected_gallery
        assert run["reader_seen"]==sorted(seen) and run["final_reader"]==visible
        if native_events_all is not None:assert native_events_all==native_events
        native_events_all=native_events
        summaries.append({"ui_events":len(ui_events),"keyboard_events":sum(e["source"]=="keyboard" for e in ui_events),
                          "gallery_pages":len(expected_gallery),"seen":sorted(seen)})
    return {"events":native_events_all,"entries":len(entries),"pages":sum(len(e[1]) for e in entries.values()),
            "catalog_sha256":sha(path.read_bytes()),"controls":summaries}


def paint_reader(px, page, palette, alpha, images=None):
    if page is None:
        return
    assert page["Box"] == [16,16,624,256]
    for y in range(16,256):
        left = 32 if y < 32 else 16
        start = (y*640+left)*4
        px[start:start+(624-left)*4] = bytes([*palette[0],255])*(624-left)
    if page.get("Image"):
        from ui_journal_illustrations_check import paint
        paint(px,page,images)
    rows=[page["Heading"]]+page["Lines"]
    if page.get("Footer"):
        rows += [""]*(14-len(rows))+[page["Footer"]]
    for row, text in enumerate(rows):
        assert row < 15 and len(text) <= (37 if row==0 else 38)
        color = palette[14 if row == 0 else 15]
        left = 32 if row == 0 else 16
        for col, ch in enumerate(text):
            assert ch in alpha and len(alpha[ch]) == 320 and not any(alpha[ch][256:])
            for off, value in enumerate(alpha[ch][:256]):
                if value:
                    yy,xx = divmod(off,16)
                    pos = ((16+16*row+yy)*640+left+16*col+xx)*4
                    for c in range(3):
                        px[pos+c] = (color[c]*value+px[pos+c]*(255-value)+127)//255


def check_reader_x11(folder, run):
    """核對具名 X11 視窗與同一步的實際 GPU 畫格，不用排版模型充當視窗。"""
    import json
    from PIL import Image
    captures = sorted(folder.glob("reader-[0-9]"))
    if not captures:
        return 0
    assert run.get("reader_interactive")
    for capture in captures:
        state=json.loads((capture/"latest.json").read_text())
        info=json.loads((capture/"x11-capture.json").read_text())
        assert state["step"]==info["step"]==810000000 and state["reader_stable"]
        assert state["reader_seen"]==[54] and not state["held"]
        assert info["width"]==640 and info["height"]==400
        matches=[f for f,s in zip(run["frames"],run["list_frames"]) if f["File"]==state["file"] and f["step"]==state["step"]
                 and s["reader"] and s["reader"]["Entry"]==state["reader_entry"]
                 and s["reader"].get("Number",1)==state["reader_page"]]
        assert matches, "X11 擷取找不到對應 GPU 畫格"
        with Image.open(capture/"actual-window.ppm") as actual, Image.open(folder/state["file"]) as expected:
            assert actual.size==expected.size==(640,400) and actual.convert("RGB").tobytes()==expected.convert("RGB").tobytes(), "X11 視窗與 GPU 畫格不同"
    return len(captures)
