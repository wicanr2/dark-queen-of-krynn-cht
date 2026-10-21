"""建立以幽靈騎士為優先的本機術語表與逐條名稱對齊候選，不自動改寫劇情。"""

import argparse
from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path


def rows(path):
    with path.open(encoding="utf-8",newline="") as stream:
        return list(csv.DictReader(stream,delimiter="\t",quoting=csv.QUOTE_NONE))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("primary",type=Path)
    parser.add_argument("secondary",type=Path)
    parser.add_argument("catalog",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("--additions",type=Path)
    args=parser.parse_args()
    terms,provenance={},[]
    conflicts=[]
    for project,root in (("death_knight_of_krynn",args.primary),("champions_of_krynn",args.secondary)):
        glossary=root/"text/glossary.tsv"
        lexicon=root/"text/name-lexicon-five.tsv"
        for path in (glossary,lexicon):
            if not path.is_file():
                if root==args.primary:
                    raise FileNotFoundError(path)
                continue
            provenance.append({"project":project,"path":str(path),"sha256":hashlib.sha256(path.read_bytes()).hexdigest()})
        for row in rows(glossary):
            key=(row["en"].casefold(),row["category"])
            value={"en":row["en"],"zh":row["zh"],"category":row["category"],"project":project,
                "file":"text/glossary.tsv","source":row["source"],"note":row["note"]}
            if key not in terms:
                terms[key]=value
            elif terms[key]["zh"]!=row["zh"]:
                conflicts.append({"selected":terms[key],"alternative":value})
        names_seen={r["en"].casefold() for r in terms.values()}
        for row in (rows(lexicon) if lexicon.is_file() else []):
            if row["en"].casefold() not in names_seen:
                terms[(row["en"].casefold(),"name") ]={"en":row["en"],"zh":row["zh"],"category":"name",
                    "project":project,"file":"text/name-lexicon-five.tsv","source":"name catalog","note":""}
                names_seen.add(row["en"].casefold())
    if args.additions:
        provenance.append({"project":"dark_queen_of_krynn","path":str(args.additions),
            "sha256":hashlib.sha256(args.additions.read_bytes()).hexdigest()})
        existing_names={r["en"].casefold() for r in terms.values()}
        for row in rows(args.additions):
            if row["en"].casefold() in existing_names:
                continue
            terms[(row["en"].casefold(),row["category"]) ]={"en":row["en"],"zh":row["zh"],
                "category":row["category"],"project":"dark_queen_of_krynn","file":"local additions",
                "source":row["source"],"note":row["note"]}
            existing_names.add(row["en"].casefold())
    args.output.mkdir(parents=True,exist_ok=True)
    ordered=sorted(terms.values(),key=lambda r:(r["category"],r["en"].casefold()))
    with (args.output/"glossary.tsv").open("w",encoding="utf-8",newline="") as stream:
        writer=csv.writer(stream,delimiter="\t",quoting=csv.QUOTE_NONE,quotechar=None,lineterminator="\n")
        writer.writerow(["en","zh","category","project","file","source","note"])
        writer.writerows([r[c] for c in ("en","zh","category","project","file","source","note")] for r in ordered)
    by_name=defaultdict(list)
    for row in ordered:
        by_name[row["en"].casefold()].append(row)
    exact=[]
    ambiguous=[]
    entries=json.loads(args.catalog.read_text())["entries"]
    for entry in entries:
        options=by_name.get(entry["text"].casefold(),[])
        if not options:
            continue
        choices={r["zh"] for r in options}
        if len(choices)==1:
            exact.append({"key":entry["key"],"source_sha256":entry["sha256"],"text":choices.pop(),
                "status":"canonical-name-candidate; context check required","terms":options})
        else:
            ambiguous.append({"key":entry["key"],"terms":options})
    result={"primary":"death_knight_of_krynn","inputs":provenance,"terms":len(ordered),
        "candidates":exact,"ambiguous":ambiguous,"retained_alternatives":conflicts}
    (args.output/"terminology-provenance.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    with (args.output/"name-candidates.tsv").open("w",encoding="utf-8",newline="") as stream:
        writer=csv.writer(stream,delimiter="\t",quoting=csv.QUOTE_NONE,quotechar=None,lineterminator="\n")
        writer.writerow(["key","text","status"])
        writer.writerows((r["key"],r["text"],r["status"]) for r in exact)
    print(json.dumps({"terms":len(ordered),"exact_name_candidates":len(exact),
        "ambiguous":len(ambiguous),"retained_alternatives":len(conflicts)},ensure_ascii=False))


if __name__=="__main__":
    main()
