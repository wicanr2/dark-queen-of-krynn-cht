#!/usr/bin/env bash
# DRAFT：真正鍵盤操作的角色選單研究入口，不是完整中文版本。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROBE="$ROOT/workplace/probe"
TEXTS="$ROOT/workplace/translation"
ORIG="$ROOT/workplace/input/dos/drkqueen"
INPUT_RUN="${DQK_MENU_INPUT_RUN:-interactive-menu-inputs-20261022}"
[[ "$INPUT_RUN" =~ ^[a-z0-9][a-z0-9-]+$ ]]
INPUT="$PROBE/$INPUT_RUN"
GO_IMAGE=sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581
PIL_IMAGE=sha256:44d0742ca1061bcd453440cdce925afa31c5324e115fca1334da0e364f0e2c48
FONT="${DQK_FONT_DIR:-/home/anr2/cht/golden_box/death_knight_of_krynn/font}"
test -d "$PROBE"
test -f "$ORIG/DQK.EXE"
test "$(stat -c %u "$PROBE")" = "$(id -u)"
test "$(stat -c %g "$PROBE")" = "$(id -g)"
case "${1:-}" in
  prepare)
    test -f "$TEXTS/en.tsv"
    test -f "$TEXTS/zh-TW.tsv"
    test -f "$PROBE/early-observe/zh-TW.tsv"
    test ! -e "$INPUT"
    timeout 30s docker run --rm --network none --memory 512m --cpus 1 --pids-limit 64 \
      --user "$(id -u):$(id -g)" --label project=dark-queen-of-krynn-cht \
      -v "$ROOT/tools:/tools:ro" -v "$TEXTS:/catalogs:ro" -v "$PROBE:/out" \
      "$PIL_IMAGE" python3 /tools/menu_live_inputs.py /catalogs /out/early-observe/zh-TW.tsv "/out/$INPUT_RUN"
    ;;
  build)
    test -f "$INPUT/zh-TW.tsv"
    test -f "$FONT/jf-openhuninn-2.1.ttf"
    test "$(stat -c %u "$INPUT")" = "$(id -u)"
    if test -e "$PROBE/x11-menu-driver"; then test "$(stat -c %u "$PROBE/x11-menu-driver")" = "$(id -u)"; fi
    bash "$ROOT/tools/early-live.sh" build
    timeout 30s docker run --rm --network none --memory 512m --cpus 1 --pids-limit 64 \
      --user "$(id -u):$(id -g)" --label project=dark-queen-of-krynn-cht \
      -v "$ROOT/tools:/tools:ro" -v "$INPUT:/out" -v "$FONT:/font:ro" \
      "$PIL_IMAGE" python3 /tools/menu_glyphs.py /font/jf-openhuninn-2.1.ttf /out/zh-TW.tsv /out/glyphs-20.json
    timeout 30s docker run --rm --network none --memory 256m --cpus 1 --pids-limit 32 \
      --user "$(id -u):$(id -g)" --label project=dark-queen-of-krynn-cht \
      -v "$ROOT/tools:/tools:ro" -v "$PROBE:/out" "$GO_IMAGE" \
      cc -std=c11 -O2 -Wall -Wextra -Werror /tools/x11_menu_driver.c -lX11 -o /out/x11-menu-driver
    MODULES="${DQK_GOMODCACHE:-/home/anr2/cht/dosgolem/workplace/gomodcache}"
    test -d "$MODULES"
    test -f "$ROOT/workplace/dosgolem/go.mod"
    if test -e "$PROBE/interactive-replay"; then test "$(stat -c %u "$PROBE/interactive-replay")" = "$(id -u)"; fi
    timeout 120s docker run --rm --init --network none --memory 2g --cpus 2 --pids-limit 128 \
      --user "$(id -u):$(id -g)" --label project=dark-queen-of-krynn-cht \
      -v "$ROOT/workplace/dosgolem:/src:ro" -v "$ROOT/tools:/tools:ro" -v "$PROBE:/out" \
      -v "$MODULES:/modules:ro" -e GOCACHE=/out/gocache -e GOMODCACHE=/modules -e GOPROXY=off -w /src \
      --entrypoint /usr/local/go/bin/go "$GO_IMAGE" build -o /out/interactive-replay /tools/interactive_replay.go
    ;;
  verify)
    FIRST_RUN="${2:-}"; SECOND_RUN="${3:-}"
    [[ "$FIRST_RUN" =~ ^[a-z0-9][a-z0-9-]+$ && "$SECOND_RUN" =~ ^[a-z0-9][a-z0-9-]+$ ]]
    test -f "$PROBE/$FIRST_RUN/receipt.json"
    test -f "$PROBE/$SECOND_RUN/receipt.json"
    test -f "$INPUT/inputs.json"
    test -f "$TEXTS/en.tsv"
    test -f "$TEXTS/zh-TW.tsv"
    timeout 60s docker run --rm --network none --memory 512m --cpus 1 --pids-limit 64 \
      --user "$(id -u):$(id -g)" --label project=dark-queen-of-krynn-cht \
      -v "$ROOT/tools:/tools:ro" -v "$TEXTS:/catalogs:ro" -v "$PROBE:/out" -v "$INPUT:/inputs:ro" \
      "$PIL_IMAGE" python3 /tools/check_interactive_menu.py /out /inputs "$FIRST_RUN" "$SECOND_RUN"
    ;;
  replay)
    RUN_NAME="${2:-}"
    [[ "$RUN_NAME" =~ ^[a-z0-9][a-z0-9-]+$ ]]
    test -f "$PROBE/$RUN_NAME/receipt.json"
    test -f "$PROBE/interactive-replay"
    test ! -e "$PROBE/$RUN_NAME-control"
    timeout 120s docker run --rm --init --network none --memory 1g --cpus 1 --pids-limit 64 \
      --user "$(id -u):$(id -g)" --label project=dark-queen-of-krynn-cht \
      -v "$ORIG:/orig:ro" -v "$PROBE:/out" -e GOMEMLIMIT=768MiB \
      --entrypoint /out/interactive-replay "$GO_IMAGE" "/out/$RUN_NAME/receipt.json" "/out/$RUN_NAME-control"
    ;;
  smoke|smoke-adventure|preview)
    RUN_NAME="${2:-}"
    [[ "$RUN_NAME" =~ ^[a-z0-9][a-z0-9-]+$ ]]
    test ! -e "$PROBE/$RUN_NAME"
    test -f "$PROBE/early-live"
    test -f "$INPUT/zh-TW.tsv"
    test -f "$INPUT/glyphs-20.json"
    if test "$1" = preview; then
      : "${DISPLAY:?需要主機 X11 顯示}"
      XAUTH="${XAUTHORITY:-$HOME/.Xauthority}"
      test -f "$XAUTH"
      test -d /tmp/.X11-unix
      timeout --kill-after=10s 600s docker run --rm --init --network none --memory 1g --cpus 2 --pids-limit 128 \
        --user "$(id -u):$(id -g)" --label project=dark-queen-of-krynn-cht \
        -v "$ORIG:/orig:ro" -v "$INPUT:/inputs:ro" -v "$PROBE:/out" \
        -v /tmp/.X11-unix:/tmp/.X11-unix:ro -v "$XAUTH:/tmp/xauth:ro" \
        -e DISPLAY="$DISPLAY" -e XAUTHORITY=/tmp/xauth -e GOMEMLIMIT=384MiB \
        --entrypoint /out/early-live "$GO_IMAGE" -interactive -lifecycle -out "/out/$RUN_NAME" \
        -catalog /inputs/zh-TW.tsv -glyphs /inputs/glyphs-20.json
      exit
    fi
    test -f "$PROBE/x11-menu-driver"
    ROUTE=roundtrip
    if test "$1" = smoke-adventure; then ROUTE=adventure; fi
    timeout --kill-after=10s 180s docker run --rm --init --network none --memory 1g --cpus 2 --pids-limit 128 \
      --user "$(id -u):$(id -g)" --label project=dark-queen-of-krynn-cht \
      -v "$ORIG:/orig:ro" -v "$INPUT:/inputs:ro" -v "$PROBE:/out" \
      -e DQK_RUN="$RUN_NAME" -e DQK_ROUTE="$ROUTE" -e GOMEMLIMIT=384MiB "$GO_IMAGE" bash -c '
        set -e
        app_pid=""; xvfb_pid=""
        cleanup() { if test -n "$app_pid"; then kill "$app_pid" 2>/dev/null || true; wait "$app_pid" 2>/dev/null || true; fi; if test -n "$xvfb_pid"; then kill "$xvfb_pid" 2>/dev/null || true; wait "$xvfb_pid" 2>/dev/null || true; fi; }
        trap cleanup EXIT
        Xvfb :99 -screen 0 800x600x24 -nolisten tcp > "/out/${DQK_RUN}-xvfb.log" 2>&1 & xvfb_pid=$!
        for attempt in {1..50}; do test -S /tmp/.X11-unix/X99 && break; sleep 0.1; done
        export DISPLAY=:99 LIBGL_ALWAYS_SOFTWARE=1
        /out/early-live -interactive -lifecycle -out "/out/$DQK_RUN" \
          -catalog /inputs/zh-TW.tsv -glyphs /inputs/glyphs-20.json > "/out/${DQK_RUN}-app.log" 2>&1 & app_pid=$!
        /out/x11-menu-driver "$app_pid" "/out/$DQK_RUN" "$DQK_ROUTE"
        wait "$app_pid"; app_pid=""
        cat /sys/fs/cgroup/memory.events > "/out/$DQK_RUN/memory-events.txt"'
    ;;
  *) echo '用法：bash tools/interactive-menu.sh prepare|build|smoke 新名|smoke-adventure 新名|replay 原操作名|verify 取消名 冒險名|preview 新名' >&2; exit 2 ;;
esac
