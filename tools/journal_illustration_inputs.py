"""DRAFT：由已驗正文輸入與三則重繪證據建立私有圖文閱讀輸入。"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path
from PIL import Image
from journal_diagrams import read_catalog


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_catalog(path, rows):
    assert all(k and v and not any(c in k+v for c in "\t\r\n") for k,v in rows.items())
    path.write_text("key\ttext\n"+"".join(f"{k}\t{v}\n" for k,v in rows.items()))


def prepare(base, book, maps, shards, ui, output):
    assert not output.exists() and output.parent.is_dir()
    reader = read_catalog(base/"reader.zh-TW.tsv")
    assert len(reader) == 132
    titles = read_catalog(book)
    new_ui = read_catalog(ui)
    assert set(new_ui) == {"reader.image_hint"} and len(new_ui["reader.image_hint"]) <= 38
    source_indices = {"maps": json.loads((maps/"evidence.json").read_text()), "shards": json.loads((shards/"evidence.json").read_text())}
    additions = dict(new_ui)
    illustrations, sources = [], []
    for entry, folder, name, source_index in ((12,shards,"shards-redraw-r3.png","shards"),
                                              (25,maps,"map25-redraw-r3.png","maps"),
                                              (64,maps,"map64-redraw-r3.png","maps")):
        source = folder/name
        assert sha(source) == source_indices[source_index]["artifacts"][name]
        with Image.open(source) as image:
            assert image.format == "PNG"
            width,height = image.size
        assert 64 < height <= 4096 and 0 < width <= 4096
        key = f"journal.{entry}.title"
        assert key not in reader and f"journal.{entry}.body" not in reader
        additions[key] = titles[key]
        illustrations.append({"entry":entry,"file":f"journal-{entry}.png","sha256":sha(source),"crop":[0,64,width,height]})
        sources.append({"entry":entry,"source":name,"source_index_sha256":sha(folder/"evidence.json"),"source_kind":"vector redraw rendered by indexed tools"})
    assert not reader.keys() & additions.keys()
    reader.update(additions)
    font = read_catalog(base/"font-zh-TW.tsv")
    for key,value in reader.items():
        assert key not in font or font[key] == value
        font[key] = value
    output.mkdir()
    for name in ("en.tsv","zh-TW.tsv","inputs.json","provenance.json"):
        shutil.copyfile(base/name,output/name)
    write_catalog(output/"reader.zh-TW.tsv",reader)
    write_catalog(output/"font-zh-TW.tsv",font)
    for item,folder in zip(illustrations,(shards,maps,maps)):
        source = folder/("shards-redraw-r3.png" if item["entry"]==12 else f'map{item["entry"]}-redraw-r3.png')
        shutil.copyfile(source,output/item["file"])
    manifest={"draft":True,"entries":illustrations}
    (output/"illustrations.json").write_text(json.dumps(manifest,indent=2)+"\n")
    provenance=json.loads((output/"provenance.json").read_text())
    provenance.update(reader_base_catalog_sha256=sha(base/"reader.zh-TW.tsv"),
                      reader_catalog_sha256=sha(output/"reader.zh-TW.tsv"),
                      reader_illustrations_sha256=sha(output/"illustrations.json"),
                      reader_image_ui_sha256=sha(ui),reader_image_book_sha256=sha(book))
    (output/"provenance.json").write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+"\n")
    (output/"illustration-provenance.json").write_text(json.dumps({"draft":True,"sources":sources,
        "base_reader_sha256":sha(base/"reader.zh-TW.tsv"),"book_sha256":sha(book),"image_ui_sha256":sha(ui),
        "reader_catalog_sha256":sha(output/"reader.zh-TW.tsv"),"rights":"local-only original-derived redraws; no scans embedded",
        "limit":"component and optional runtime prototype, not new original-game citations"},ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"entries":67,"prose":64,"illustrations":3,"reader_rows":len(reader)},ensure_ascii=False))


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("base","book","maps","shards","ui","output"): parser.add_argument(name,type=Path)
    args=parser.parse_args()
    prepare(args.base,args.book,args.maps,args.shards,args.ui,args.output)
