"""檢查本機試譯 TSV 與字型覆蓋，另產生供閱讀的雙語校對稿。"""

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re
import unicodedata


FORMAT = re.compile(r"%(?:[-+ #0]*\d*(?:\.\d+)?[hlL]?[diuoxXfFeEgGcrsp%])")


def load(path, header):
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    if "\r" in text:
        raise ValueError(f"{path.name} 含 CR")
    rows = list(csv.reader(text.splitlines(), delimiter="\t", quoting=csv.QUOTE_NONE))
    if not rows or rows[0] != header:
        raise ValueError(f"{path.name} 表頭不符")
    if any(len(row) != len(header) for row in rows[1:]):
        raise ValueError(f"{path.name} 欄數不符")
    keys = [row[0] for row in rows[1:]]
    if len(keys) != len(set(keys)):
        raise ValueError(f"{path.name} key 重複")
    return [dict(zip(header,row)) for row in rows[1:]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source",type=Path)
    parser.add_argument("trial",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("--font",type=Path,required=True)
    parser.add_argument("--style-approved",action="store_true",help="僅在使用者明確確認此批譯風後使用")
    parser.add_argument("--glossary",type=Path)
    parser.add_argument("--batch-id",default="trial")
    args = parser.parse_args()
    source = {row["key"]:row["text"] for row in load(args.source,["key","text"])}
    rows = load(args.trial,["key","text","note"])
    existing={}
    if (args.output/"zh-TW.tsv").is_file():
        existing={r["key"]:r["text"] for r in load(args.output/"zh-TW.tsv",["key","text"])}
    from fontTools.ttLib import TTFont
    with TTFont(args.font) as font:
        coverage = set().union(*(table.cmap.keys() for table in font["cmap"].tables if table.isUnicode()))
    errors=[f"既有譯文孤兒 key：{key}" for key in existing if key not in source]
    term_warnings=[]
    chars=set()
    canon = {}
    all_canon={}
    term_reviews=[]
    review_path=args.output/"term-reviews.tsv"
    if review_path.is_file():
        term_reviews=load(review_path,["key","term","source_sha256","translation_sha256","reason"])
    applied_reviews=[]
    if args.glossary:
        with args.glossary.open(encoding="utf-8") as stream:
            for item in csv.DictReader(stream,delimiter="\t",quoting=csv.QUOTE_NONE):
                all_canon.setdefault(item["en"].casefold(),set()).add(item["zh"])
                if item["category"] in ("item","monster","person"):
                    canon.setdefault(item["en"].casefold(),set()).add(item["zh"])
    for row in rows:
        key,text = row["key"],row["text"]
        if key not in source:
            errors.append(f"孤兒 key：{key}")
            continue
        if not text or text != text.strip() or unicodedata.normalize("NFC",text) != text:
            errors.append(f"空白或正規化：{key}")
        if any(unicodedata.category(c)=="Cc" for c in text):
            errors.append(f"控制字元：{key}")
        if Counter(FORMAT.findall(source[key])) != Counter(FORMAT.findall(text)):
            errors.append(f"格式參數：{key}")
        source_numbers=Counter(re.findall(r"\d+",source[key]))
        target_numbers=Counter(re.findall(r"\d+",text))
        # 前作的法術級數以中文序數命名，核對數值等價，不能為通過檢查改寫既有名稱。
        level=re.fullmatch(r"([1-9])(?:st|nd|rd|th) Level",source[key])
        if level and text=="第"+"一二三四五六七八九"[int(level[1])-1]+"級":
            target_numbers=Counter([level[1]])
        if source_numbers != target_numbers:
            errors.append(f"數字需複核：{key}")
        names=canon.get(source[key].casefold(),set())
        if len(names)==1 and text not in names:
            errors.append(f"名稱未對齊幽靈騎士：{key}")
        matches=[]
        for term,choices in all_canon.items():
            for match in re.finditer(r"(?<![a-z0-9])"+re.escape(term)+r"s?(?![a-z0-9])",source[key].casefold()):
                matches.append((match.start(),match.end(),term,choices))
        picked=[]
        for match in sorted(matches,key=lambda m:-(m[1]-m[0])):
            if not any(match[0]<prev[1] and prev[0]<match[1] for prev in picked):
                picked.append(match)
        for begin,end,term,choices in picked:
            if term in canon and len(choices)==1:
                expected=next(iter(choices))
                if expected not in text:
                    known=next((r for r in term_reviews if r["key"]==key and r["term"]==term
                        and r["source_sha256"]==hashlib.sha256(source[key].encode()).hexdigest()
                        and r["translation_sha256"]==hashlib.sha256(text.encode()).hexdigest()),None)
                    if known:
                        applied_reviews.append(known)
                    else:
                        term_warnings.append({"key":key,"term":term,"expected":expected,
                            "note":"句內術語需語境核對；不自動改寫譯文"})
        chars.update(text)
    missing = sorted(c for c in chars if not c.isspace() and ord(c) not in coverage)
    errors.extend(f"缺字：{c}" for c in missing)
    args.output.mkdir(parents=True,exist_ok=True)
    report = {"style_approved":args.style_approved,"runtime_integrated":False,
        "rows":len(rows),"characters":sum(len(r["text"]) for r in rows),
        "unique_characters":len(chars),"errors":errors,"font_sha256":hashlib.sha256(args.font.read_bytes()).hexdigest(),
        "term_warnings":term_warnings,
        "term_reviews_applied":applied_reviews,
        "tool_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "glossary_sha256":hashlib.sha256(args.glossary.read_bytes()).hexdigest() if args.glossary else None,
        "input_sha256":hashlib.sha256(args.trial.read_bytes()).hexdigest(),
        "source_sha256":hashlib.sha256(args.source.read_bytes()).hexdigest()}
    if not re.fullmatch(r"[a-z0-9-]+",args.batch_id):
        raise ValueError("批次名稱格式不符")
    (args.output/(args.batch_id+"-check.json")).write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    state = "使用者已確認本批譯風，尚未接入正式遊戲。" if args.style_approved else "試譯待確認，尚未接入正式遊戲。"
    review = ["# 《黑暗之后》繁中試譯", "", "狀態："+state, "",
        "範圍：角色選單、帕蘭薩斯、凱爾高斯與出航。來源與譯文只留本機。", ""]
    for row in rows:
        review += [f'## {row["key"]}',"",source.get(row["key"],"缺少來源"),"",row["text"],"",row["note"],""]
    (args.output/(args.batch_id+"-review.md")).write_text("\n".join(review),encoding="utf-8")
    if args.style_approved and not errors:
        completed=args.output/"completed"
        completed.mkdir(exist_ok=True)
        archive=completed/(args.batch_id+"-"+report["input_sha256"][:20]+".tsv")
        if archive.exists() and archive.read_bytes()!=args.trial.read_bytes():
            raise ValueError("已完成批次的雜湊身分衝突")
        if not archive.exists():
            archive.write_bytes(args.trial.read_bytes())
        report_text=json.dumps(report,ensure_ascii=False,indent=2)+"\n"
        report_id=hashlib.sha256(report_text.encode()).hexdigest()[:20]
        receipt=completed/(archive.stem+"-"+report_id+".json")
        if receipt.exists() and receipt.read_text()!=report_text:
            raise ValueError("已完成收據的雜湊身分衝突")
        if not receipt.exists():
            receipt.write_text(report_text)
        merged=existing.copy()
        for row in rows:
            merged[row["key"]]=row["text"]
        with (args.output/"zh-TW.tsv").open("w",encoding="utf-8",newline="") as stream:
            writer=csv.writer(stream,delimiter="\t",quoting=csv.QUOTE_NONE,quotechar=None,lineterminator="\n")
            writer.writerow(["key","text"])
            writer.writerows(merged.items())
    print(json.dumps({"rows":len(rows),"style_approved":args.style_approved,
        "errors":errors,"term_warnings":len(term_warnings),"term_reviews_applied":len(applied_reviews),
        "input_sha256":report["input_sha256"],"runtime_integrated":False},ensure_ascii=False))
    if errors:
        raise SystemExit(1)


if __name__=="__main__":
    main()
