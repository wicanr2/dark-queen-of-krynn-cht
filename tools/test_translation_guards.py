"""在 Docker 內驗證譯文檢查器拒絕破壞格式、名稱或既有譯表的批次。"""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def write(path,header,rows):
    with path.open("w",encoding="utf-8",newline="") as stream:
        writer=csv.writer(stream,delimiter="\t",quoting=csv.QUOTE_NONE,quotechar=None,lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("font",type=Path)
    args=parser.parse_args()
    checker=Path(__file__).with_name("translation_check.py")
    with tempfile.TemporaryDirectory(prefix="dqk-translation-check-") as directory:
        root=Path(directory)
        source=root/"en.tsv"
        glossary=root/"glossary.tsv"
        write(source,["key","text"],[("format","takes %d%s"),("name","Spectre"),("level","1st Level"),
            ("context","A fine for dragons")])
        write(glossary,["en","zh","category"],[("Spectre","幽靈","monster"),("Fine","精良","item"),
            ("Dragon","龍族","monster")])
        cases={"valid":[("format","受到%d%s","fixture"),("name","幽靈","fixture"),("level","第一級","fixture")],
            "orphan":[("unknown","未知","fixture")],
            "placeholder":[("format","受到%d","fixture")],
            "name":[("name","幽魂","fixture")],
            "number":[("level","第二級","fixture")],
            "duplicate":[("name","幽靈","fixture"),("name","幽靈","fixture")],
            "multi-review":[("context","罰款與龍群","fixture")],
            "duplicate-review":[("context","罰款與龍群","fixture")],
            "review-only":[("format","受到%d%s","fixture")]}
        passed=[]
        for name,rows in cases.items():
            output=root/name
            output.mkdir()
            # 每次先放入已存在譯文，錯誤批次不得清空或重寫它。
            target=output/"zh-TW.tsv"
            write(target,["key","text"],[("name","幽靈")])
            if name=="review-only":
                # 候選來源可屬另一份清單；純校讀不能合併或驗成既有語系表。
                write(target,["key","text"],[("other-catalog-only","既有譯文")])
            before=hashlib.sha256(target.read_bytes()).hexdigest()
            batch=output/"batch.tsv"
            write(batch,["key","text","note"],rows)
            if name=="name":
                # 即使句內警示有校讀紀錄，也不能豁免單獨名稱的錯譯。
                write(output/"term-reviews.tsv",["key","term","source_sha256","translation_sha256","reason"],
                    [("name","spectre",hashlib.sha256(b"Spectre").hexdigest(),
                      hashlib.sha256("幽魂".encode()).hexdigest(),"不得覆蓋正式名稱約束的fixture")])
            if name in ("multi-review","duplicate-review"):
                reviews=[("context",term,hashlib.sha256(b"A fine for dragons").hexdigest(),
                    hashlib.sha256("罰款與龍群".encode()).hexdigest(),"同句不同詞的語境fixture")
                    for term in ("fine","dragon")]
                if name=="duplicate-review":
                    reviews.append(reviews[0])
                write(output/"term-reviews.tsv",["key","term","source_sha256","translation_sha256","reason"],reviews)
            command=[sys.executable,str(checker),str(source),str(batch),str(output),
                "--font",str(args.font),"--glossary",str(glossary),"--style-approved"]
            if name=="review-only":
                command.append("--review-only")
            run=subprocess.run(command,
                capture_output=True,text=True,timeout=15)
            if name=="review-only":
                assert run.returncode==0,run.stderr+run.stdout
                assert hashlib.sha256(target.read_bytes()).hexdigest()==before,name
                assert not (output/"completed").exists(),name
                report=json.loads((output/"trial-check.json").read_text())
                assert report["review_only"] and report["style_approved"]
                assert not report["errors"]
            elif name in ("valid","multi-review"):
                assert run.returncode==0,run.stderr+run.stdout
                assert list((output/"completed").glob("*.tsv"))
                if name=="multi-review":
                    report=json.loads((output/"trial-check.json").read_text())
                    assert not report["term_warnings"]
                    assert len(report["term_reviews_applied"])==2
            else:
                assert run.returncode!=0,name
                assert hashlib.sha256(target.read_bytes()).hexdigest()==before,name
                assert not (output/"completed").exists(),name
            passed.append(name)
        print(json.dumps({"passed":passed,"preserves_existing_on_error":True},ensure_ascii=False))


if __name__=="__main__":
    main()
