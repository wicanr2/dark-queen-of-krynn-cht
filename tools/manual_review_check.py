"""DRAFT：核對手冊校讀來源、前作術語、保護片段與離線排版。"""
import argparse
import base64
import csv
import hashlib
import json
from pathlib import Path
import re

from journal_diagrams import FONT_SHA, read_catalog


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wrap(body):
    result=[]
    for paragraph in body.split(r"\n"):
        if not paragraph:
            result.append("");continue
        boundaries={m.end() for m in re.finditer(r"-?\d+|[A-Za-z]+(?:[-'][A-Za-z]+)*|.",paragraph)}
        at=0
        while at<len(paragraph):
            ends=[i for i in range(at+1,min(at+38,len(paragraph))+1) if i in boundaries and
                  (i==len(paragraph) or (paragraph[i] not in "，。！？、；：」』）》】" and paragraph[i-1] not in "「『（《【"))]
            assert ends,"手冊無安全斷行"
            end=max(ends);result.append(paragraph[at:end]);at=end
    assert result and len(result)<=39,"手冊超出三頁量測容量"
    return result


def validate(project, review, prior, font, output):
    from fontTools.ttLib import TTFont
    assert not output.exists() and output.parent.is_dir()
    manifest=json.loads((review/"source-review.json").read_text())
    assert manifest["draft"] is True and manifest["runtime_verified"] is False
    assert sha(review/"operation-review.zh-TW.tsv")==manifest["review_sha256"]
    assert sha(font)==FONT_SHA
    texts=read_catalog(review/"operation-review.zh-TW.tsv")
    ui=read_catalog(review/"reader-ui.zh-TW.tsv")
    assert set(ui)=={"manual.heading","manual.page"} and all(v.count("%s")==2 for v in ui.values())
    def source(relative, expected):
        path=(project/relative).resolve()
        assert path.is_relative_to(project.resolve()) and path.is_file()
        assert sha(path)==expected,("來源雜湊不符",relative)
    for row in manifest["sources"]: source(row["path"],row["sha256"])
    term_path=project/manifest["glossary"]["path"]
    source(manifest["glossary"]["path"],manifest["glossary"]["sha256"])
    with term_path.open() as stream: terms=list(csv.DictReader(stream,delimiter="\t"))
    assert sha(prior)==manifest["prior_glossary_sha256"]
    with prior.open() as stream: prior_terms=list(csv.DictReader(stream,delimiter="\t"))
    expected=set();font_text=dict(texts);font_text.update(ui);layouts=[]
    pages=[p["page"] for p in manifest["pages"]]
    assert pages==list(range(manifest["first_page"],manifest["last_page"]+1))
    for page in manifest["pages"]:
        number=page["page"];prefix=f"manual.operation.page{number}"
        title,body=[texts[prefix+suffix] for suffix in (".title",".body")]
        expected.update((prefix+".title",prefix+".body"))
        assert page["image"] in {r["path"] for r in manifest["sources"]}
        assert page["ocr"] in {r["path"] for r in manifest["sources"]}
        assert page["source_level"]=="scan reviewed" and page["panel"] in ("review-only","hold-password-scope")
        for text in (title,body):
            assert not any(ord(c)<32 or c=="�" for c in text)
            # 原手冊的 DOS 路徑保留反斜線；其餘只接受 TSV 換行語法。
            without_paths=re.sub(r"\b[A-Z]:\\[A-Z0-9._\\]+", "", text)
            assert not re.search(r"\\(?!n)",without_paths)
        heading=ui["manual.heading"] % (number,title)
        assert len(heading)<=37
        lines=wrap(body);count=(len(lines)+12)//13
        for part in range(count):
            font_text[f"expanded.heading.{number}.{part}"]=heading
            font_text[f"expanded.footer.{number}.{part}"]=ui["manual.page"] % (part+1,count)
        layouts.append({"page":number,"lines":len(lines),"parts":count,"panel":page["panel"]})
    assert set(texts)==expected,"手冊缺頁或含孤兒鍵"
    for binding in manifest["terms"]:
        matching=[t for t in terms if t["en"]==binding["en"] and t["category"]==binding["category"]]
        assert len(matching)==1
        body=texts[f'manual.operation.page{binding["page"]}.body']
        assert matching[0]["zh"] in body,("術語未對齊",binding)
        previous=[t for t in prior_terms if t["en"]==binding["en"] and t["category"]==binding["category"]]
        if previous: assert len(previous)==1 and previous[0]["zh"]==matching[0]["zh"],("前作術語衝突",binding)
    for fact in manifest["invariants"]:
        body=texts[f'manual.operation.page{fact["page"]}.body']
        assert all(s in body for s in fact["required"]),("校讀片段遺失",fact["page"])
        assert all(s not in body for s in fact.get("forbidden",[])),("舊誤植回流",fact["page"])
    all_chars=set("".join(v.replace(r"\n", "") for v in font_text.values()))
    cmap=TTFont(font).getBestCmap()
    assert all(ord(c) in cmap for c in all_chars),"手冊字型缺字"
    assert {p["page"] for p in manifest["pages"] if p["panel"]=="hold-password-scope"}==set(manifest["hold_pages"])
    output.mkdir()
    (output/"font-source.tsv").write_text("key\ttext\n"+"".join(f"{k}\t{v}\n" for k,v in font_text.items()))
    result={"draft":True,"source_pages":len(pages),"review_rows":len(texts),"characters":sum(len(v) for v in texts.values()),
            "glyphs":len(all_chars),"term_bindings":len(manifest["terms"]),"protected_facts":len(manifest["invariants"]),
            "hold_pages":manifest["hold_pages"],"layouts":layouts,"review_sha256":sha(review/"operation-review.zh-TW.tsv"),
            "checker_sha256":sha(Path(__file__)),"limits":"source proofread and offline layout only; no manual panel or runtime rule validation"}
    (output/"review-check.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:result[k] for k in ("source_pages","review_rows","characters","glyphs","term_bindings","hold_pages")},ensure_ascii=False))


def layout(review, output):
    from PIL import Image
    texts=read_catalog(review/"operation-review.zh-TW.tsv");ui=read_catalog(review/"reader-ui.zh-TW.tsv")
    checked=json.loads((output/"review-check.json").read_text())
    assert sha(review/"operation-review.zh-TW.tsv")==checked["review_sha256"]
    glyphs=json.loads((output/"glyphs-16.json").read_text())
    assert glyphs["size"]==16 and glyphs["height"]==20
    alpha={c:base64.b64decode(v) for c,v in glyphs["glyphs"].items()}
    assert all(len(v)==320 and not any(v[256:]) for v in alpha.values())
    dest=output/"pages";assert not dest.exists();dest.mkdir()
    images=[]
    for entry in checked["layouts"]:
        if entry["panel"]!="review-only":continue
        page=entry["page"];prefix=f"manual.operation.page{page}"
        lines=wrap(texts[prefix+".body"])
        for part in range(entry["parts"]):
            image=Image.new("RGB",(640,400),"black")
            rows=[ui["manual.heading"] % (page,texts[prefix+".title"])]+lines[part*13:part*13+13]
            rows += [""]*(14-len(rows))+[ui["manual.page"] % (part+1,entry["parts"])]
            for y,text in enumerate(rows):
                assert y<15 and len(text)<=(37 if y==0 else 38)
                for x,char in enumerate(text):
                    mask=Image.frombytes("L",(16,20),alpha[char]).crop((0,0,16,16))
                    left=(32 if y==0 else 16)+x*16;top=16+y*16
                    image.paste((255,255,85) if y==0 else (255,255,255),(left,top,left+16,top+16),mask)
            file=dest/f"page{page:02d}-{part+1}.png";image.save(file);images.append({"file":str(file.relative_to(output)),"sha256":sha(file)})
    (output/"layout-check.json").write_text(json.dumps({"draft":True,"images":images,"held":checked["hold_pages"],"not_game_capture":True},indent=2)+"\n")
    print("手冊離線量測圖：",len(images))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("mode",choices=("validate","layout"));parser.add_argument("paths",nargs="+",type=Path)
    args=parser.parse_args()
    if args.mode=="validate": validate(*args.paths)
    else: layout(*args.paths)
