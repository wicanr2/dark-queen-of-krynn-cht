"""核對整句來源元件的原版負向路徑及離線測試，不作 GUI 驗收。"""
import json
from pathlib import Path
import shutil
import sys

from bar_ui_inputs import audit,write
from literal_catalog import read,sha

BASE="passage-chain-20261024"
TOOLS=("passage_chain_source.py","passage_chain_probe.go","ui_passage_source.go","ui_passage_source_test.go",
       "passage_chain_inputs.py","bar_ui_inputs.py","literal_catalog.py","text_catalog.py","ui_list_inputs.py")


def comparable(a,b):
    for k in ("exe_sha256","state_sha256","request_sha256","source_commit","go_version","request","checkpoints"):
        assert a[k]==b[k],k
    assert a["source_commit"]=="f79eab6db8c64a524a06535e53e5d32b0bbcf7c8" and a["go_version"]=="go1.24.13"
    assert a["exe_sha256"]=="3b41fb06a045568b0c35098a104499d489d8a5c0ef0dd48a039387ba2393ba58"
    assert not a["pending_paragraphs"] and not b["pending_paragraphs"]
    for c in a["checkpoints"]:assert not c["file_writes"] and not c["unimplemented"]


def native(root,output):
    probe=root/"workplace/probe";base=probe/BASE
    legacy=sha(base/"programs-r1/passage-chain-probe");binary=sha(output/"programs-r1/passage-chain-probe")
    book={"registry_sha256":sha(base/"chain-inputs-r1/registry.json"),"en_sha256":sha(base/"chain-inputs-r1/en.tsv")}
    reports=[]
    for label,first,second,expected,count in [
        ("forest-pair","observe-forest-r1","control-forest-r1",legacy,72),
        ("book-bar-pair","observe-book-bar-r1","control-book-bar-r1",binary,5),
    ]:
        a,b=[read(output/n/"receipt.json") for n in (first,second)];comparable(a,b)
        assert a["observe"] and not b["observe"] and not b["paragraphs"]
        assert a["probe_sha256"]==b["probe_sha256"]==expected and len(a["checkpoints"])==count
        for c in a["checkpoints"]:assert sha(output/first/(c["label"]+".png"))==sha(output/second/(c["label"]+".png"))
        assert sha(output/first/"final.state")==sha(output/second/"final.state")
        if label=="forest-pair":
            assert not a["paragraphs"]
            assert a["state_sha256"]==sha(probe/"battle-text-20261024/control-journey-r2/final.state")
            assert a["request_sha256"]==sha(output/"forest-request-r1.json")
        else:
            assert len(a["paragraphs"])==4
            assert a["passage_source_files"]==b["passage_source_files"]==book
            assert a["passage_candidate_parts"]==b["passage_candidate_parts"]==0
            assert all(p["passage_candidates"]==[] for p in a["paragraphs"])
        reports.append(dict(label=label,checkpoints=count,paragraphs=len(a["paragraphs"] or []),matched_parts=0))
    old=read(base/"observe-bar-r1/receipt.json")
    enabled=read(output/"observe-book-bar-r1/receipt.json");default=read(output/"observe-default-bar-r1/receipt.json")
    for a,name in [(enabled,"observe-book-bar-r1"),(default,"observe-default-bar-r1")]:
        comparable(a,old)
        assert a["probe_sha256"]==binary
        assert [{k:v for k,v in p.items() if k!="passage_candidates"} for p in a["paragraphs"]]==old["paragraphs"]
        assert a["script_files"]==old["script_files"]
        for c in old["checkpoints"]:assert sha(output/name/(c["label"]+".png"))==sha(base/"observe-bar-r1"/(c["label"]+".png"))
        assert sha(output/name/"final.state")==sha(base/"observe-bar-r1/final.state")
    assert "passage_source_files" not in default and "passage_candidate_parts" not in default
    current=read(output/"observe-book-forest-r1/receipt.json");previous=read(output/"control-forest-r1/receipt.json")
    comparable(current,previous)
    assert current["probe_sha256"]==binary and current["passage_source_files"]==book
    assert current["passage_candidate_parts"]==0 and not current["paragraphs"]
    for c in current["checkpoints"]:assert sha(output/"observe-book-forest-r1"/(c["label"]+".png"))==sha(output/"control-forest-r1"/(c["label"]+".png"))
    assert sha(output/"observe-book-forest-r1/final.state")==sha(output/"control-forest-r1/final.state")
    write(output/"native-source-check.json",dict(reports=reports,normal_unique_checkpoints=77,
        default_bar_equal_legacy=True,enabled_bar_equal_legacy=True,enabled_forest_checkpoints_equal=72,
        source_book=book,normal_chain_observed=False,limits="四次酒館來源不誤認；森林移動未觸發目標 ECL 來源，不是整句執行、中文或 GUI 驗收。"))


def evidence(root,output):
    report=read(output/"native-source-check.json");assert report["normal_unique_checkpoints"]==77 and not report["normal_chain_observed"]
    log=(output/"source-tests-r1.log").read_text()
    assert "SKIP" not in log and "FAIL" not in log
    for n in ("TestPassageSourceRealArchive","TestPassageSourceRejectsMismatch","TestPassageSourceRealBarFallback"):
        assert "--- PASS: "+n in log
    assert "999" in log and log.count("--- PASS: TestPassageSourceRejectsMismatch/")==18
    fixed=read(output/"source-run.json")
    for n,h in fixed["source_files"].items():assert sha(root/"tools"/n)==sha(output/"programs-r1"/n)==h
    assert fixed["binary_sha256"]==sha(output/"programs-r1/passage-chain-probe")==read(output/"binary-rebuild.json")["sha256"]
    parent=root/"workplace/probe/combat-effects-20261024/evidence.json"
    old=read(parent);sources=[parent,root/"workplace/input/dos/drkqueen/DQK.EXE",root/"workplace/input/dos/drkqueen/DISK3/ECL.GLB",
        root/"workplace/probe/passage-chain-20261024/evidence.json",root/"workplace/probe/passage-chain-20261024/chain-inputs-r1/registry.json",
        root/"workplace/probe/passage-chain-20261024/chain-inputs-r1/en.tsv",root/"workplace/probe/passage-chain-20261024/chain-inputs-r1/zh-TW.review.tsv",
        root/"workplace/probe/battle-text-20261024/control-journey-r2/final.state",root/"workplace/probe/pane-render-20261022/observe-palace-journal-r1/final.state"]
    for row in old["sources"]:
        if row["path"].startswith("workplace/translation/"):
            p=root/row["path"];assert sha(p)==row["sha256"];sources.append(p)
    snapshots=output/"tool-snapshots";snapshots.mkdir()
    for n in TOOLS:shutil.copy2(root/"tools"/n,snapshots/n)
    def item(p):return dict(path=str(p.relative_to(root)),bytes=p.stat().st_size,sha256=sha(p))
    write(output/"evidence.json",dict(draft=True,sources=[item(p) for p in sources],artifacts=[item(p) for p in sorted(output.rglob("*")) if p.is_file() and p.name!="evidence.json"],
        tools={n:sha(root/"tools"/n) for n in TOOLS},native=report,offline=dict(groups=144,occurrences=155,fragment_keys=306,wrap_checks=999,guards=18),
        docker_images=fixed["docker_images"],
        limits="辨識元件及只讀原版候選探針。沒有整句正常正向來源、GUI、分頁或時序驗收；現行翻譯及呈現程式不變。"))


if __name__=="__main__":globals()[sys.argv[1]](*map(Path,sys.argv[2:4]))
