"""以原版段落與校讀 TSV 獨立檢查單頁手札，不呼叫 Go 排版。"""
def reader_model(inputs, config, native_paragraphs, accepted, runs):
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
            bindings = [f for f in config["Paragraphs"] if f["Key"] == event["detail"]["page"]["Key"]]
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


def paint_reader(px, page, palette, alpha):
    if page is None:
        return
    assert page["Box"] == [16,16,624,256]
    for y in range(16,256):
        left = 32 if y < 32 else 16
        start = (y*640+left)*4
        px[start:start+(624-left)*4] = bytes([*palette[0],255])*(624-left)
    for row, text in enumerate([page["Heading"]]+page["Lines"]):
        assert row < 14 and len(text) <= 38
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
