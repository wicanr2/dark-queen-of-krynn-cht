#!/usr/bin/env bash
# 本作已確認譯風後的本機文字流程，原始輸入與前作唯讀。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$ROOT/workplace"
DKK="${DQK_DKK_DIR:-/home/anr2/cht/golden_box/death_knight_of_krynn}"
COK="${DQK_COK_DIR:-/home/anr2/cht/golden_box/champions_of_krynn}"
PIL_IMAGE=sha256:44d0742ca1061bcd453440cdce925afa31c5324e115fca1334da0e364f0e2c48
FONT_IMAGE=sha256:6d849051db2e108262fa689160011dc64045cc402f61985548a525559d3a1cf3
GO_IMAGE=sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581
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
  passages)
    test -f "$WORK/translation/catalog.json"
    test -f "$WORK/input/dos/drkqueen/DISK3/ECL.GLB"
    timeout 30s docker run --rm --init --label project=dark-queen-of-krynn-cht \
      --network none --memory 512m --cpus 1 --pids-limit 64 --user "$(id -u):$(id -g)" \
      --entrypoint python3 -v "$ROOT/tools:/tools:ro" -v "$WORK/translation:/out" \
      -v "$WORK/input/dos/drkqueen:/orig:ro" "$PIL_IMAGE" /tools/passage_candidates.py \
      /orig/DISK3/ECL.GLB /out/catalog.json /out
    ;;
  chain-fixture)
    RUN_NAME="${2:-}"
    [[ "$RUN_NAME" =~ ^[a-z0-9][a-z0-9-]+$ ]]
    RUN_DIR="$WORK/probe/$RUN_NAME"
    MODULES="${DQK_GOMODCACHE:-/home/anr2/cht/dosgolem/workplace/gomodcache}"
    test -d "$WORK/probe"
    test -d "$WORK/probe/gocache"
    test -d "$MODULES"
    test -f "$WORK/dosgolem/go.mod"
    test -f "$WORK/probe/startup/adventure-start.state"
    test -f "$WORK/input/dos/drkqueen/DQK.EXE"
    test ! -e "$RUN_DIR"
    test "$(git -C "$WORK/dosgolem" rev-parse HEAD)" = f79eab6db8c64a524a06535e53e5d32b0bbcf7c8
    git -C "$WORK/dosgolem" diff --exit-code HEAD -- .
    timeout 30s docker run --rm --init --label project=dark-queen-of-krynn-cht \
      --network none --memory 512m --cpus 1 --pids-limit 64 --user "$(id -u):$(id -g)" \
      --entrypoint python3 -v "$ROOT/tools:/tools:ro" -v "$WORK/probe:/out" \
      -v "$WORK/input/dos/drkqueen:/orig:ro" "$PIL_IMAGE" /tools/make_text_chain_fixture.py \
      /orig "/out/$RUN_NAME"
    timeout 120s docker run --rm --init --label project=dark-queen-of-krynn-cht \
      --network none --memory 2g --cpus 2 --pids-limit 128 --user "$(id -u):$(id -g)" \
      -e GOCACHE=/gocache -e GOMODCACHE=/modules -e GOPROXY=off -e GOMAXPROCS=2 \
      -v "$WORK/dosgolem:/src:ro" -v "$ROOT/tools:/tools:ro" -v "$RUN_DIR:/out" \
      -v "$WORK/probe/gocache:/gocache" -v "$MODULES:/modules:ro" -w /src \
      --entrypoint /usr/local/go/bin/go "$GO_IMAGE" build -o /out/story-probe /tools/story_text_probe.go
    for VARIANT in direct-11 prefix-18-11; do
      test -d "$RUN_DIR/$VARIANT/game"
      test -d "$RUN_DIR/$VARIANT/trace"
      timeout 180s docker run --rm --init --label project=dark-queen-of-krynn-cht \
        --network none --memory 1g --cpus 1 --pids-limit 64 --user "$(id -u):$(id -g)" \
        -e GOMEMLIMIT=768MiB -e GOMAXPROCS=1 -v "$RUN_DIR:/bin-input:ro" \
        -v "$WORK/probe/startup:/states:ro" -v "$RUN_DIR/$VARIANT/game:/orig:ro" \
        -v "$RUN_DIR/$VARIANT/trace:/out" --entrypoint /bin-input/story-probe "$GO_IMAGE" \
        /states/adventure-start.state /out
    done
    timeout 30s docker run --rm --init --label project=dark-queen-of-krynn-cht \
      --network none --memory 512m --cpus 1 --pids-limit 64 --user "$(id -u):$(id -g)" \
      --entrypoint python3 -v "$ROOT/tools:/tools:ro" -v "$RUN_DIR:/out" \
      -v "$WORK/probe/startup:/states:ro" -v "$WORK/input/dos/drkqueen:/orig:ro" \
      "$PIL_IMAGE" /tools/make_text_chain_fixture.py /orig /out --verify \
      --snapshot /states/adventure-start.state --probe /out/story-probe
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
  check-passages)
    test -f "$WORK/translation/passage-candidates.en.tsv"
    test -d "$WORK/translation/passage-review"
    test -f "$WORK/translation/passage-review/zh-TW.review.tsv"
    test -f "$WORK/translation/glossary.tsv"
    test -f "$DKK/font/jf-openhuninn-2.1.ttf"
    timeout 30s docker run --rm --init --label project=dark-queen-of-krynn-cht \
      --network none --memory 512m --cpus 1 --pids-limit 64 --user "$(id -u):$(id -g)" \
      --entrypoint python3 -v "$ROOT/tools:/tools:ro" -v "$WORK/translation:/input:ro" \
      -v "$WORK/translation/passage-review:/out" -v "$DKK/font:/font:ro" \
      "$FONT_IMAGE" /tools/translation_check.py /input/passage-candidates.en.tsv \
      /out/zh-TW.review.tsv /out --font /font/jf-openhuninn-2.1.ttf \
      --style-approved --review-only --glossary /input/glossary.tsv --batch-id passage-review
    ;;
  test)
    test -f "$DKK/font/jf-openhuninn-2.1.ttf"
    timeout 30s docker run --rm --init --label project=dark-queen-of-krynn-cht \
      --network none --memory 512m --cpus 1 --pids-limit 64 --user "$(id -u):$(id -g)" \
      --entrypoint python3 -v "$ROOT/tools:/tools:ro" -v "$DKK/font:/font:ro" \
      "$FONT_IMAGE" /tools/test_translation_guards.py /font/jf-openhuninn-2.1.ttf
    ;;
  *) echo '用法：bash tools/translation.sh extract|terms|seed|batches|passages|check-passages|chain-fixture 新輸出名|check [批次名稱]|test' >&2; exit 2 ;;
esac
