#!/usr/bin/env bash
# 本作已確認譯風後的本機文字流程，原始輸入與前作唯讀。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$ROOT/workplace"
DKK="${DQK_DKK_DIR:-/home/anr2/cht/golden_box/death_knight_of_krynn}"
COK="${DQK_COK_DIR:-/home/anr2/cht/golden_box/champions_of_krynn}"
PIL_IMAGE=sha256:44d0742ca1061bcd453440cdce925afa31c5324e115fca1334da0e364f0e2c48
FONT_IMAGE=sha256:6d849051db2e108262fa689160011dc64045cc402f61985548a525559d3a1cf3
test -d "$WORK"
case "${1:-}" in
  extract)
    test -d "$WORK/translation"
    test -d "$WORK/input/dos/drkqueen"
    test -d "$WORK/probe"
    test -f "$WORK/input/dos/drkqueen/DQK.EXE"
    test -f "$WORK/input/dos/drkqueen/DISK3/ECL.GLB"
    test -f "$WORK/input/dos/drkqueen/DISK2/MONCHA.GLB"
    test -f "$WORK/probe/early-observe/trace.json"
    test -f "$WORK/probe/story-observe/trace.json"
    timeout 30s docker run --rm --init --label project=dark-queen-of-krynn-cht \
      --network none --memory 512m --cpus 1 --pids-limit 64 --user "$(id -u):$(id -g)" \
      --entrypoint python3 -v "$ROOT/tools:/tools:ro" -v "$WORK/input/dos/drkqueen:/orig:ro" \
      -v "$WORK/probe:/receipts:ro" -v "$WORK/translation:/out" \
      "$PIL_IMAGE" /tools/text_catalog.py /orig /out \
      --trace /receipts/early-observe/trace.json --trace /receipts/story-observe/trace.json
    ;;
  terms|seed)
    test -f "$WORK/translation/catalog.json"
    test -f "$DKK/text/glossary.tsv"
    test -f "$COK/text/glossary.tsv"
    if test "$1" = terms; then
      test -f "$DKK/text/name-lexicon-five.tsv"
      test -f "$WORK/translation/glossary-additions.tsv"
      ARGUMENTS=(/tools/terminology_align.py /dkk /cok /out/catalog.json /out
        --additions /out/glossary-additions.tsv)
    else
      ARGUMENTS=(/tools/translation_seed.py /out/catalog.json /out --previous /dkk --previous /cok)
    fi
    timeout 30s docker run --rm --init --label project=dark-queen-of-krynn-cht \
      --network none --memory 512m --cpus 1 --pids-limit 64 --user "$(id -u):$(id -g)" \
      --entrypoint python3 -v "$ROOT/tools:/tools:ro" -v "$WORK/translation:/out" \
      -v "$DKK:/dkk:ro" -v "$COK:/cok:ro" "$PIL_IMAGE" "${ARGUMENTS[@]}"
    ;;
  batches)
    test -f "$WORK/translation/catalog.json"
    test -f "$WORK/translation/name-candidates.tsv"
    timeout 30s docker run --rm --init --label project=dark-queen-of-krynn-cht \
      --network none --memory 256m --cpus 1 --pids-limit 64 --user "$(id -u):$(id -g)" \
      --entrypoint python3 -v "$ROOT/tools:/tools:ro" -v "$WORK/translation:/out" \
      "$PIL_IMAGE" /tools/translation_batches.py /out
    ;;
  check)
    BATCH="${2:-trial}"
    [[ "$BATCH" =~ ^[a-z0-9-]+$ ]]
    case "$BATCH" in
      trial) FILE=trial.zh-TW.tsv ;;
      names) FILE=batch-names.tsv ;;
      *) FILE="$BATCH.tsv" ;;
    esac
    test -f "$WORK/translation/$FILE"
    test -f "$WORK/translation/en.tsv"
    test -f "$WORK/translation/glossary.tsv"
    test -f "$DKK/font/jf-openhuninn-2.1.ttf"
    timeout 30s docker run --rm --init --label project=dark-queen-of-krynn-cht \
      --network none --memory 512m --cpus 1 --pids-limit 64 --user "$(id -u):$(id -g)" \
      --entrypoint python3 -v "$ROOT/tools:/tools:ro" -v "$WORK/translation:/out" \
      -v "$DKK/font:/font:ro" "$FONT_IMAGE" /tools/translation_check.py \
      /out/en.tsv "/out/$FILE" /out --font /font/jf-openhuninn-2.1.ttf \
      --style-approved --glossary /out/glossary.tsv --batch-id "$BATCH"
    ;;
  test)
    test -f "$DKK/font/jf-openhuninn-2.1.ttf"
    timeout 30s docker run --rm --init --label project=dark-queen-of-krynn-cht \
      --network none --memory 512m --cpus 1 --pids-limit 64 --user "$(id -u):$(id -g)" \
      --entrypoint python3 -v "$ROOT/tools:/tools:ro" -v "$DKK/font:/font:ro" \
      "$FONT_IMAGE" /tools/test_translation_guards.py /font/jf-openhuninn-2.1.ttf
    ;;
  *) echo '用法：bash tools/translation.sh extract|terms|seed|batches|check [批次名稱]|test' >&2; exit 2 ;;
esac
