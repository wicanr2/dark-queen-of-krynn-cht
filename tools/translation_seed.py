"""依原文 SHA-256 收集前作一致譯文，保留待校對狀態，不直接升格為正式譯文。"""

import argparse
import csv
import hashlib
import json
from pathlib import Path


def read_tsv(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream,delimiter="\t",quoting=csv.QUOTE_NONE))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("--previous",type=Path,action="append",required=True)
    args=parser.parse_args()
    catalog=json.loads(args.catalog.read_text())
    candidates,inputs={},[]
    priority=[p.name for p in args.previous]
    for previous in args.previous:
        for domain in ("ecl-text","ui-text","name"):
            events=previous/"text"/(domain+"-events.tsv")
            translations=previous/"text"/(domain+".zh-TW.tsv")
            if not events.is_file() or not translations.is_file():
                continue
            for p in (events,translations):
                inputs.append({"path":str(p),"sha256":hashlib.sha256(p.read_bytes()).hexdigest()})
            source={r["event_key"]:r["original_sha256"] for r in read_tsv(events)}
            for row in read_tsv(translations):
                key=row["key"]
                if key in source and row.get("translation","").strip():
                    candidates.setdefault(source[key],[]).append({"translation":row["translation"],
                        "project":previous.name,"key":key,"source":row.get("source","")})
    args.output.mkdir(parents=True,exist_ok=True)
    seeds,conflicts=[],[]
    for entry in catalog["entries"]:
        matches=candidates.get(entry["sha256"],[])
        match_type="exact"
        if not matches and "%" not in entry["text"]:
            # 純文字可對照前作全大寫及標題式大小寫，含格式參數時禁止改寫大小寫。
            variants={entry["text"].upper(),entry["text"].lower(),entry["text"].title()}
            matches=[row for text in sorted(variants) for row in
                candidates.get(hashlib.sha256(text.encode("ascii")).hexdigest(),[])]
            if matches:
                match_type="case-only"
        selected=next((p for p in priority if any(row["project"]==p for row in matches)),None)
        preferred=[row for row in matches if row["project"]==selected]
        choices={row["translation"] for row in preferred}
        if len(choices)==1:
            seeds.append({"key":entry["key"],"text":choices.pop(),
                "status":f"prior-{match_type}; needs-context-review","selected_project":selected,"matches":matches})
        elif len(choices)>1:
            conflicts.append({"key":entry["key"],"matches":matches})
    with (args.output/"prior-candidates.tsv").open("w",encoding="utf-8",newline="") as stream:
        writer=csv.writer(stream,delimiter="\t",quoting=csv.QUOTE_NONE,quotechar=None,lineterminator="\n")
        writer.writerow(["key","text","status"])
        writer.writerows((r["key"],r["text"],r["status"]) for r in seeds)
    result={"inputs":inputs,"seeded":len(seeds),"conflicts":conflicts,"entries":seeds}
    (args.output/"prior-provenance.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"prior_candidates":len(seeds),"conflicts":len(conflicts)},ensure_ascii=False))


if __name__=="__main__":
    main()
