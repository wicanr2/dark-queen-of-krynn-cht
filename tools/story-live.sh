#!/usr/bin/env bash
# DRAFT：正常首段劇情的實際視窗字級比較，不是遊戲啟動器。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROBE="$ROOT/workplace/probe"
ORIG="$ROOT/workplace/input/dos/drkqueen"
TEXTS="$ROOT/workplace/translation"
SEQUENCE="${DQK_STORY_SEQUENCE:-$PROBE/story-return-sequence-20261022}"
FONT="${DQK_FONT_DIR:-/home/anr2/cht/golden_box/death_knight_of_krynn/font}"
GO_IMAGE=sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581
PIL_IMAGE=sha256:44d0742ca1061bcd453440cdce925afa31c5324e115fca1334da0e364f0e2c48
test -d "$PROBE"
test -f "$ORIG/DQK.EXE"
test -f "$PROBE/startup/adventure-start.state"
test -f "$TEXTS/en.tsv"
test -f "$TEXTS/zh-TW.tsv"
test "$(stat -c %u "$PROBE")" = "$(id -u)"
test "$(stat -c %g "$PROBE")" = "$(id -g)"
case "${1:-}" in
  probe-build)
    MODULES="${DQK_GOMODCACHE:-/home/anr2/cht/dosgolem/workplace/gomodcache}"
    test -d "$MODULES"
    test -d "$PROBE/gocache"
    test -f "$ROOT/workplace/dosgolem/go.mod"
    test "$(git -C "$ROOT/workplace/dosgolem" rev-parse HEAD)" = f79eab6db8c64a524a06535e53e5d32b0bbcf7c8
    git -C "$ROOT/workplace/dosgolem" diff --exit-code HEAD -- .
    if test -e "$PROBE/story-sequence-probe"; then
      test "$(stat -c %u "$PROBE/story-sequence-probe")" = "$(id -u)"
      test "$(stat -c %g "$PROBE/story-sequence-probe")" = "$(id -g)"
    fi
    timeout 120s docker run --rm --init --network none --memory 2g --cpus 2 --pids-limit 128 \
      --user "$(id -u):$(id -g)" --label project=dark-queen-of-krynn-cht \
      -v "$ROOT/workplace/dosgolem:/src:ro" -v "$ROOT/tools:/tools:ro" -v "$PROBE:/out" \
      -v "$MODULES:/modules:ro" -e GOCACHE=/out/gocache -e GOMODCACHE=/modules \
      -e GOPROXY=off -e GOMAXPROCS=2 -w /src --entrypoint /usr/local/go/bin/go \
      "$GO_IMAGE" build -o /out/story-sequence-probe /tools/story_text_probe.go
    ;;
  probe|probe-control|hall-probe|hall-probe-control|city-state|save-probe|save-probe-control|camp-lifecycle)
    RUN_NAME="${2:-}"
    case "$RUN_NAME" in ''|*[!A-Za-z0-9_-]*) exit 2 ;; esac
    test ! -e "$PROBE/$RUN_NAME"
    test -f "$PROBE/story-sequence-probe"
    MODE=enter-sequence
    case "$1" in probe-control) MODE=enter-sequence-control ;; hall-probe) MODE=hall-sequence ;; hall-probe-control) MODE=hall-sequence-control ;; city-state) MODE=city-state ;; save-probe) MODE=save-sequence ;; save-probe-control) MODE=save-sequence-control ;; camp-lifecycle) MODE=camp-lifecycle ;; esac
    timeout 120s docker run --rm --init --network none --memory 1g --cpus 1 --pids-limit 64 \
      --user "$(id -u):$(id -g)" --label project=dark-queen-of-krynn-cht \
      -v "$ORIG:/orig:ro" -v "$PROBE:/out" -v "$PROBE/startup:/states:ro" -e GOMEMLIMIT=768MiB -e GOMAXPROCS=1 \
      --entrypoint /out/story-sequence-probe "$GO_IMAGE" \
      /states/adventure-start.state "/out/$RUN_NAME" "$MODE"
    ;;
  prepare)
    test -f "$SEQUENCE/trace.json"
    test -f "$FONT/jf-openhuninn-2.1.ttf"
    test "$(stat -c %u "$SEQUENCE")" = "$(id -u)"
    test "$(stat -c %g "$SEQUENCE")" = "$(id -g)"
    test ! -e "$SEQUENCE/runtime-zh-TW.tsv"
    timeout 30s docker run --rm --network none --memory 512m --cpus 1 --pids-limit 64 \
      --user "$(id -u):$(id -g)" --label project=dark-queen-of-krynn-cht \
      -v "$ROOT/tools:/tools:ro" -v "$SEQUENCE:/out" -v "$TEXTS:/catalogs:ro" -v "$FONT:/font:ro" \
      "$PIL_IMAGE" python3 /tools/story_preview.py /out /font/jf-openhuninn-2.1.ttf --runtime-inputs /catalogs
    ;;
  build)
    test -f "$SEQUENCE/trace.json"
    test -f "$FONT/jf-openhuninn-2.1.ttf"
    test "$(stat -c %u "$SEQUENCE")" = "$(id -u)"
    test "$(stat -c %g "$SEQUENCE")" = "$(id -g)"
    test -f "$SEQUENCE/runtime-zh-TW.tsv"
    bash "$ROOT/tools/early-live.sh" build
    for SIZE in 16 20; do
      TARGET="$SEQUENCE/glyphs-$SIZE.json"
      if test -e "$TARGET"; then
        test "$(stat -c %u "$TARGET")" = "$(id -u)"
        test "$(stat -c %g "$TARGET")" = "$(id -g)"
      fi
      timeout 30s docker run --rm --network none --memory 512m --cpus 1 --pids-limit 64 \
        --user "$(id -u):$(id -g)" --label project=dark-queen-of-krynn-cht \
        -v "$ROOT/tools:/tools:ro" -v "$SEQUENCE:/out" -v "$FONT:/font:ro" \
        "$PIL_IMAGE" python3 /tools/menu_glyphs.py /font/jf-openhuninn-2.1.ttf \
        /out/runtime-zh-TW.tsv "/out/glyphs-$SIZE.json" "$SIZE"
    done
    ;;
  en|16|20|fine-20|fine-en|sequence-20|sequence-16|sequence-en)
    test -f "$SEQUENCE/trace.json"
    test -f "$PROBE/early-live"
    SIZE=20; TRANSLATE=true; FINE=false; SEQUENCE_MODE=false
    case "$1" in en|sequence-en) TRANSLATE=false ;; 16|sequence-16) SIZE=16 ;; fine-20) FINE=true ;; fine-en) TRANSLATE=false; FINE=true ;; esac
    case "$1" in sequence-*) SEQUENCE_MODE=true ;; esac
    test -f "$SEQUENCE/glyphs-$SIZE.json"
    RUN_NAME="${2:-live-story-$1}"
    case "$RUN_NAME" in ''|*[!A-Za-z0-9_-]*) exit 2 ;; esac
    test ! -e "$PROBE/$RUN_NAME"
    timeout 120s docker run --rm --init --network none --memory 1g --cpus 2 --pids-limit 128 \
      --user "$(id -u):$(id -g)" --label project=dark-queen-of-krynn-cht \
      -v "$ORIG:/orig:ro" -v "$PROBE:/out" -v "$TEXTS:/catalogs:ro" -v "$SEQUENCE:/sequence:ro" \
      -e DQK_RUN="$RUN_NAME" -e DQK_SIZE="$SIZE" -e DQK_TRANSLATE="$TRANSLATE" -e DQK_FINE="$FINE" \
      -e DQK_SEQUENCE="$SEQUENCE_MODE" \
      -e GOMEMLIMIT=384MiB "$GO_IMAGE" bash -c '
        set -e
        Xvfb :99 -screen 0 800x600x24 -nolisten tcp > "/out/${DQK_RUN}-xvfb.log" 2>&1 &
        xvfb_pid=$!
        trap "kill $xvfb_pid 2>/dev/null; wait $xvfb_pid 2>/dev/null" EXIT
        for attempt in {1..50}; do test -S /tmp/.X11-unix/X99 && break; sleep 0.1; done
        export DISPLAY=:99 LIBGL_ALWAYS_SOFTWARE=1
        set +e
        /out/early-live -state /out/startup/adventure-start.state -out "/out/${DQK_RUN}" \
          -catalog /sequence/runtime-zh-TW.tsv -source-catalog /catalogs/en.tsv \
          -glyphs "/sequence/glyphs-${DQK_SIZE}.json" -story \
          -translate="$DQK_TRANSLATE" -fine="$DQK_FINE" -story-sequence="$DQK_SEQUENCE"
        result=$?
        cat /sys/fs/cgroup/memory.events > "/out/${DQK_RUN}/memory-events.txt"
        exit "$result"'
    ;;
  *) echo '用法：bash tools/story-live.sh probe-build|probe 新名|probe-control 新名|hall-probe 新名|hall-probe-control 新名|city-state 新名|save-probe 新名|save-probe-control 新名|camp-lifecycle 新名|prepare|build|en|16|20|fine-20|fine-en|sequence-20|sequence-16|sequence-en [全新輸出名]' >&2; exit 2 ;;
esac
