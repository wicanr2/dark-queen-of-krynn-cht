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
        write(source,["key","text"],[("format","takes %d%s"),("name","Spectre"),("level","1st Level")])
        write(glossary,["en","zh","category"],[("Spectre","幽靈","monster")])
        cases={"valid":[("format","受到%d%s","fixture"),("name","幽靈","fixture"),("level","第一級","fixture")],
            "orphan":[("unknown","未知","fixture")],
            "placeholder":[("format","受到%d","fixture")],
            "name":[("name","幽魂","fixture")],
            "number":[("level","第二級","fixture")],
            "duplicate":[("name","幽靈","fixture"),("name","幽靈","fixture")]}
        passed=[]
        for name,rows in cases.items():
            output=root/name
            output.mkdir()
            # 每次先放入已存在譯文，錯誤批次不得清空或重寫它。
            target=output/"zh-TW.tsv"
            write(target,["key","text"],[("name","幽靈")])
            before=hashlib.sha256(target.read_bytes()).hexdigest()
            batch=output/"batch.tsv"
            write(batch,["key","text","note"],rows)
            if name=="name":
                # 即使句內警示有校讀紀錄，也不能豁免單獨名稱的錯譯。
                write(output/"term-reviews.tsv",["key","term","source_sha256","translation_sha256","reason"],
                    [("name","spectre",hashlib.sha256(b"Spectre").hexdigest(),
                      hashlib.sha256("幽魂".encode()).hexdigest(),"不得覆蓋正式名稱約束的fixture")])
            run=subprocess.run([sys.executable,str(checker),str(source),str(batch),str(output),
                "--font",str(args.font),"--glossary",str(glossary),"--style-approved"],
                capture_output=True,text=True,timeout=15)
            if name=="valid":
                assert run.returncode==0,run.stderr+run.stdout
                assert list((output/"completed").glob("*.tsv"))
            else:
                assert run.returncode!=0,name
                assert hashlib.sha256(target.read_bytes()).hexdigest()==before,name
                assert not (output/"completed").exists(),name
            passed.append(name)
        print(json.dumps({"passed":passed,"preserves_existing_on_error":True},ensure_ascii=False))


if __name__=="__main__":
    main()
