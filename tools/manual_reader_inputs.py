"""由已校讀手冊建立獨立說明面板資料，不改原版規則或手札已讀。"""
import csv
import json
from pathlib import Path
import shutil
import sys

from manual_review_check import wrap
from journal_diagrams import read_catalog as catalog
from original_prefix_check import read
from passage_runtime_inputs import record, sha, write

BASE = "status-menu-20261025/inputs-r1"
MANUAL = "manual-gameplay-20261023"
BODY_SOURCES = ("appendix-r1/supplement-review", "appendix-r1/core-review",
                "adventurer-core-r1", "adventurer-monsters-r1", "adventurer-spells-r1")
TABLE_SOURCES = ("appendix-r1/supplement-review", "appendix-r1")


def lines(text):
    return [line for p in text.split(r"\n") for line in (wrap(p) if p else [""])]


def derive(root, ui):
    base = root / "workplace/probe" / MANUAL
    values, books, sources, source_pages = dict(ui), {}, {}, {}
    def source(path):
        sources[str(path.relative_to(root))] = record(path)
    source(root / "text/manual-ui.zh-TW.tsv")
    def merge(path):
        data = catalog(path)
        assert not set(data) & values.keys(), path
        values.update(data)
        source(path)
        return data
    for name in BODY_SOURCES:
        folder = base / name
        manifest = read(folder / "source-review.json")
        text = merge(folder / "operation-review.zh-TW.tsv")
        assert sha(folder / "operation-review.zh-TW.tsv") == manifest["review_sha256"]
        assert not manifest["runtime_verified"] and not manifest["hold_pages"]
        source(folder / "source-review.json")
        for item in manifest["sources"]:
            path = root / item["path"]
            assert path.resolve().is_relative_to(root.resolve()) and sha(path) == item["sha256"]
        key_prefix = manifest.get("key_prefix", "manual.operation")
        book = key_prefix.split(".")[1]
        docs = books.setdefault(book, [])
        for page in manifest["pages"]:
            n = page["page"]
            prefix = key_prefix+".page"+str(n)
            kind = "illustration-pending" if page["panel"] == "illustration-only" else "body"
            assert prefix+".title" in text
            body = prefix+".body" if kind == "body" else "manual.image_pending"
            assert (prefix+".body" in text) == (kind == "body")
            docs.append(dict(id=prefix, source_page=n, title_key=prefix+".title", body_key=body, kind=kind))
            source_pages.setdefault(book, []).append(n)
    assert source_pages == {"operation":list(range(1,60)), "adventurer":list(range(1,82))}
    table_count = cells_count = literal_count = 0
    row_groups=[]
    for name in TABLE_SOURCES:
        folder = base / name
        manifest = read(folder / "tables.json")
        source(folder / "tables.json")
        source(folder / "table-cells.tsv")
        assert sha(folder / "table-cells.tsv") == manifest["cells_sha256"]
        text = merge(folder / "tables.zh-TW.tsv")
        assert sha(folder / "tables.zh-TW.tsv") == manifest["translation_sha256"]
        with (folder / "table-cells.tsv").open() as f:
            rows = list(csv.DictReader(f, delimiter="\t"))
        raw = {(r["table"],r["row"],r["field"]):r["value"] for r in rows}
        assert len(raw) == len(rows)
        used = set()
        for table in manifest["tables"]:
            tid = table["id"]
            prefix = "table."+tid
            chunks = lines(text[prefix+".note"])+[""]
            for row in table["rows"]:
                row_lines=[]
                for field in table["fields"]:
                    fid = field["id"]
                    cell = tid,row,fid
                    used.add(cell)
                    value = text[prefix+".row."+row+"."+fid]
                    if field["kind"] == "literal":
                        assert value == raw[cell]
                        literal_count += 1
                    elif field["kind"] == "mapped":
                        assert value == field["values"][raw[cell]]
                    else:
                        assert field["kind"] == "label"
                    row_lines.extend(lines(ui["manual.cell"] % (text[prefix+".column."+fid],value)))
                assert 0<len(row_lines)<=13,"附表單筆超出頁面，須另立帶標頭的分頁規格"
                if len(chunks)%13+len(row_lines)>13:
                    chunks.extend([""]*(13-len(chunks)%13))
                start=len(chunks)
                chunks.extend(row_lines)
                row_groups.append(dict(table=tid,row=row,start=start,count=len(row_lines)))
                assert start//13==(len(chunks)-1)//13
                if len(chunks)%13:chunks.append("")
            key = prefix+".reader_body"
            assert key not in values
            values[key] = r"\n".join(chunks)
            books.setdefault("appendix", []).append(dict(id=prefix, source_page=table["source_page"],
                 title_key=prefix+".title", body_key=key, kind="table"))
            table_count += 1
        assert used == raw.keys()
        cells_count += len(raw)
    assert table_count == 50 and cells_count == 3379
    entries = []
    for book, docs in books.items():
        for doc in docs:
            heading = ui["manual.document_heading"] % (ui["manual.book."+book], doc["source_page"], values[doc["title_key"]])
            assert len(heading) <= 37,(doc["id"],heading)
            body = lines(values[doc["body_key"]])
            assert len(body) <= 8192 and all(len(l)<=38 for l in body)
            for start in range(0,len(body),13):
                assert len(ui["manual.document_hint"] % (start//13+1,(len(body)+12)//13)) <= 38
            item = ui["manual.index_item"] % (ui["manual.selected"],doc["source_page"],values[doc["title_key"]])
            assert len(item) <= 38
            entries.append(dict(id=doc["id"],lines=len(body),pages=(len(body)+12)//13,kind=doc["kind"]))
    bundle = dict(version=1, books=[dict(id=k,title_key="manual.book."+k,documents=v) for k,v in books.items()])
    return values,bundle,dict(sources=sources, documents=entries, table_cells=cells_count,row_groups=row_groups,
                              literal_cells=literal_count, tables=table_count, source_pages=source_pages)


def prepare(root,out):
    assert not (out / "evidence.json").exists()
    source_ui=root / "text/manual-ui.zh-TW.tsv"
    if not (out / "manual-ui.zh-TW.tsv").exists():
        shutil.copyfile(source_ui,out / "manual-ui.zh-TW.tsv")
    assert sha(source_ui)==sha(out / "manual-ui.zh-TW.tsv")
    ui = catalog(out / "manual-ui.zh-TW.tsv")
    values,bundle,proof = derive(root,ui)
    required=set(ui)
    required.update(k for book in bundle["books"] for doc in book["documents"] for k in (doc["title_key"],doc["body_key"]))
    values={k:v for k,v in values.items() if k in required}
    target = out / "inputs-r1"
    assert not target.exists()
    shutil.copytree(root / "workplace/probe" / BASE,target)
    (target / "manual.zh-TW.tsv").write_text("key\ttext\n"+"".join(k+"\t"+v+"\n" for k,v in sorted(values.items())))
    write(target / "manual-index.json",bundle)
    glyph_text = catalog(target / "font-zh-TW.tsv")
    glyph_text["manual-font.existing"]="".join(sorted(read(target / "glyphs-16.json")["glyphs"]))
    glyph_text.update({"manual-font."+k:v.replace(r"\n", "") for k,v in values.items()})
    # 標題及頁碼的數字是呈現值，必須包含在字型聯集。
    glyph_text["manual-font.digits"]="0123456789"
    (target / "font-zh-TW.tsv").write_text("key\ttext\n"+"".join(k+"\t"+v+"\n" for k,v in sorted(glyph_text.items())))
    write(out / "source-proof.json",proof)
    shutil.copyfile(root / "workplace/probe/status-menu-20261025/city-request.json",out / "request.json")
    # 所有查閱控制都在原版穩定的 905M 點，前端操作期間原版不前進。
    keys=["F6","Return","PgDn","Esc"]+["Down"]*5+["Return","Esc","Right","Return","PgDn","Esc","Right","Return","PgDn","PgDn","PgUp","Esc","F6"]
    write(out / "controls.json",dict(native_request_sha256=sha(out / "request.json"),
          controls=[dict(at=905000000,key=k) for k in keys]))
    print("manual documents",len(proof["documents"]),"tables",proof["tables"],"cells",proof["table_cells"],
          "reading pages",sum(d["pages"] for d in proof["documents"]))


def seal(root,out):
    assert not (out / "evidence.json").exists()
    checked=read(out / "check.json")
    assert checked["original_state_equal"] and checked["runs"]["x11-zh"]["x11_captures"]==11
    parent=root / "workplace/probe/manual-reader-20261025"
    guard_source=(out if (out / "guards/results.tsv").exists() else parent) / "guards/results.tsv"
    assert len(guard_source.read_text().splitlines())==3
    assert read(out / "rebuild.json")["input_files"]==18
    assert (out / "binary-rebuild.log").read_text().split()[0]==sha(out / "programs-r1/ui-list-live")
    names={p.name for p in (out / "programs-r1").glob("*.go")}
    names.update(("manual_reader_inputs.py","manual_reader_check.py","manual_x11_driver.c","x11_menu_driver.c",
          "oracle_video_observer.go","oracle_input_modifier.go","manual_review_check.py","menu_glyphs.py",
          "journal_diagrams.py","original_prefix_check.py","passage_runtime_inputs.py","passage_chain_inputs.py",
          "original_prefix_inputs.py","text_catalog.py","ui_journal_reader_check.py","ui_journal_illustrations_check.py",
          "ui_list_inputs.py","ui-list-live.sh","early-live.sh"))
    snapshots=out / "tool-snapshots"
    snapshots.mkdir()
    for name in sorted(names):shutil.copyfile(root / "tools" / name,snapshots / name)
    sources=dict(read(out / "source-proof.json")["sources"])
    extra=[root / "workplace/input/dos/drkqueen" / n for n in ("DQK.EXE","DISK3/ECL.GLB")]
    extra.extend(p for p in (root / "workplace/probe" / BASE).iterdir() if p.is_file())
    extra.extend(root / "workplace/probe" / n for n in (
        "status-menu-20261025/city-control/receipt.json","status-menu-20261025/city-en/receipt.json",
        "status-menu-20261025/city-zh/receipt.json","ammo-boundaries-20261024/bolts-observe-r1/final.state",
        "journal59-route-20261025/control-r2/receipt.json","journal59-route-20261025/main-zh-r3/receipt.json",
        "captain-dialogue-20261025/control-r2/final.state"))
    for p in extra:sources[str(p.relative_to(root))]=record(p)
    if parent!=out:
        for n in ("evidence.json","guards/results.tsv","baseline-en/receipt.json","baseline-zh/receipt.json",
                  "journal-en/receipt.json","journal-zh/receipt.json"):
            p=parent/n;sources[str(p.relative_to(root))]=record(p)
    write(out / "evidence.json",dict(state="SEALED",draft=True,summary=checked,
          artifacts={str(p.relative_to(out)):record(p) for p in sorted(out.rglob("*")) if p.is_file()},
          sources=sources,tools={n:record(snapshots / n) for n in sorted(names)},
          limits="正式版面及入口未定案；現行程式及 GUI 以 programs-r1、en/zh-r2 為準，繼承的回歸另列來源。"))
    audit(root,out)


def audit(root,out):
    index=read(out / "evidence.json")
    assert index["state"]=="SEALED"
    for path,expected in index["artifacts"].items():assert record(out / path)==expected,path
    for path,expected in index["sources"].items():assert record(root / path)==expected,path
    for name,expected in index["tools"].items():assert record(out / "tool-snapshots" / name)==expected,name
    print("sealed audit",{k:len(index[k]) for k in ("artifacts","sources","tools")})


if __name__ == "__main__":
    mode,project,directory=sys.argv[1:]
    assert mode in ("prepare","seal","audit")
    globals()[mode](Path(project),Path(directory))
