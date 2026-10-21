"""由現行正式 TSV 衍生角色選單研究輸入；舊原型只提供已觀測的 key 集合。"""
import csv
import hashlib
import json
import os
from pathlib import Path
import sys


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    with path.open() as file:
        rows = list(csv.DictReader(file, delimiter="\t", quoting=csv.QUOTE_NONE))
    result = {r["key"]: r["text"] for r in rows}
    if len(result) != len(rows):
        raise ValueError("重複 key")
    return result


def main():
    catalogs, previous, output = map(Path, sys.argv[1:4])
    if output.exists() or output.parent.stat().st_uid != os.getuid():
        raise ValueError("必須使用屬於目前使用者的全新研究輸出")
    en, zh, old = read(catalogs / "en.tsv"), read(catalogs / "zh-TW.tsv"), read(previous)
    if len(old) != 12:
        raise ValueError("舊 key 集合不是十二項角色選單")
    selected, bindings = {}, []
    for full_hash in old:
        key = "ui." + full_hash[:20]
        if key not in en or key not in zh or sha(en[key].encode()) != full_hash:
            raise ValueError("現行來源與已觀測字串不符")
        selected[full_hash] = zh[key]
        bindings.append({"source_sha256": full_hash, "catalog_key": key})
    output.mkdir()
    (output / "source-en.tsv").write_bytes((catalogs / "en.tsv").read_bytes())
    (output / "source-zh-TW.tsv").write_bytes((catalogs / "zh-TW.tsv").read_bytes())
    with (output / "zh-TW.tsv").open("w") as file:
        writer = csv.writer(file, delimiter="\t", quoting=csv.QUOTE_NONE, quotechar=None, lineterminator="\n")
        writer.writerow(["key", "text"])
        writer.writerows(sorted(selected.items()))
    report = {"draft": True, "bindings": bindings,
              "en_sha256": sha((catalogs / "en.tsv").read_bytes()),
              "zh_sha256": sha((catalogs / "zh-TW.tsv").read_bytes()),
              "previous_keyset_sha256": sha(previous.read_bytes()),
              "output_sha256": sha((output / "zh-TW.tsv").read_bytes())}
    (output / "inputs.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print("已由現行 TSV 衍生十二項角色選單，舊原型譯文未作為來源。")


if __name__ == "__main__":
    main()
