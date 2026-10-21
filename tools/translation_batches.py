"""由目前 catalog 建立待譯批次與可沿用的單獨名稱批次，原始內容只留本機。"""

import argparse
import csv
import json
from pathlib import Path


def read(path):
    if not path.is_file():
        return []
    with path.open(encoding="utf-8",newline="") as stream:
        return list(csv.DictReader(stream,delimiter="\t",quoting=csv.QUOTE_NONE))


def write(path,header,rows):
    with path.open("w",encoding="utf-8",newline="") as stream:
        writer=csv.writer(stream,delimiter="\t",quoting=csv.QUOTE_NONE,quotechar=None,lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory",type=Path)
    args=parser.parse_args()
    root=args.directory
    entries=json.loads((root/"catalog.json").read_text())["entries"]
    existing={row["key"] for row in read(root/"zh-TW.tsv")}
    known={row["key"]:row for row in read(root/"name-candidates.tsv")}
    names=[(entry["key"],known[entry["key"]]["text"],"依術語對照；來源見terminology-provenance.json，尚未驗證本作顯示")
        for entry in entries if entry["key"] in known and entry["key"] not in existing]
    write(root/"batch-names.tsv",["key","text","note"],names)
    pending=[entry for entry in entries if entry["key"] not in existing and entry["key"] not in known]
    batch_dir=root/"batches"
    batch_dir.mkdir(exist_ok=True)
    index=[]
    for domain in ("ui","name","ecl"):
        selected=[entry for entry in pending if entry["domain"]==domain]
        for offset in range(0,len(selected),100):
            part=selected[offset:offset+100]
            filename=f"{domain}-{offset//100+1:03d}.tsv"
            write(batch_dir/filename,["key","original","status"],
                ((entry["key"],entry["text"],entry["status"]) for entry in part))
            index.append({"file":filename,"entries":len(part),"domain":domain})
    (batch_dir/"index.json").write_text(json.dumps({"candidate_batches":True,
        "not_a_completion_denominator":True,"batches":index},ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"existing":len(existing),"canonical_name_batch":len(names),
        "pending_candidates":len(pending),"batches":len(index)},ensure_ascii=False))


if __name__=="__main__":
    main()
