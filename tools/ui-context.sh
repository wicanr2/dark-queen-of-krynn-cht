#!/usr/bin/env bash
# DRAFT：原版介面觀測。主機只檢查路徑、Git 與呼叫 Docker。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROBE="$ROOT/workplace/probe"
ORIG="$ROOT/workplace/input/dos/drkqueen"
GO_IMAGE=sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581
PIL_IMAGE=sha256:44d0742ca1061bcd453440cdce925afa31c5324e115fca1334da0e364f0e2c48
relative() {
  [[ "$1" =~ ^[a-z0-9][a-z0-9/.-]*$ && "$1" != *..* ]]
}
test -d "$PROBE"
test "$(stat -c %u:%g "$PROBE")" = "$(id -u):$(id -g)"
case "${1:-}" in
  build)
    MODULES="${DQK_GOMODCACHE:-/home/anr2/cht/dosgolem/workplace/gomodcache}"
    test -d "$MODULES"
    test -d "$PROBE/gocache"
    test -f "$ROOT/workplace/dosgolem/go.mod"
    test -f "$ROOT/tools/ui_context_probe.go"
    test "$(git -C "$ROOT/workplace/dosgolem" rev-parse HEAD)" = f79eab6db8c64a524a06535e53e5d32b0bbcf7c8
    git -C "$ROOT/workplace/dosgolem" diff --exit-code HEAD -- .
    timeout 120s docker run --rm --init --network none --user "$(id -u):$(id -g)" \
      --memory 2g --cpus 2 --pids-limit 128 --label project=dark-queen-of-krynn-cht \
      -e HOME=/tmp -e GOCACHE=/gocache -e GOMODCACHE=/modules -e GOPROXY=off -e GOMAXPROCS=2 \
      -v "$ROOT/workplace/dosgolem:/src:ro" -v "$ROOT/tools:/tools:ro" \
      -v "$MODULES:/modules:ro" -v "$PROBE/gocache:/gocache" -v "$PROBE:/out" \
      -w /src --entrypoint bash "$GO_IMAGE" -c \
      'set -e; test ! -e /out/ui-context-probe || test "$(stat -c %u:%g /out/ui-context-probe)" = "$(id -u):$(id -g)"; printf "%s\n" "{\"Replace\":{\"/src/oracle/dqk_video_observer.go\":\"/tools/oracle_video_observer.go\"}}" >/tmp/context-overlay.json; go build -overlay /tmp/context-overlay.json -o /out/ui-context-probe /tools/ui_context_probe.go /tools/ui_menu_source.go'
    ;;
  run)
    STATE="${2:?需指定 probe 內的快照相對路徑}"
    REQUEST="${3:?需指定 probe 內的 JSON 相對路徑}"
    RESULT="${4:?需指定 probe 內的全新輸出相對路徑}"
    MODE="${5:?需指定 observe 或 control}"
    SEED="${6:-}"
    BOOT="${7:-}"
    boot_args=()
    if [[ -n "$BOOT" ]];then
      relative "$BOOT";test -f "$PROBE/$BOOT"
      [[ "$STATE" = cold ]]
      boot_args=(-e "DQK_CONTEXT_BOOT_REQUEST=/probe/$BOOT")
    fi
    seed_args=()
    if [[ -n "$SEED" ]];then
      [[ "$SEED" =~ ^[A-Za-z0-9][A-Za-z0-9/.-]*$ && "$SEED" != *..* ]]
      test -f "$PROBE/$SEED/SavGamJ.qsv";test -f "$PROBE/$SEED/VaultJ.DAT"
      seed_args=("/probe/$SEED")
    fi
    relative "$STATE"; relative "$REQUEST"; relative "$RESULT"
    [[ "$MODE" = observe || "$MODE" = control ]]
    test -f "$PROBE/ui-context-probe"
    STATE_ARG="/probe/$STATE"
    if [[ "$STATE" = cold ]];then STATE_ARG=-;else test -f "$PROBE/$STATE";fi
    test -f "$PROBE/$REQUEST"
    test -f "$ORIG/DQK.EXE"
    PARENT="$(dirname "$PROBE/$RESULT")"
    test -d "$PARENT"
    test "$(stat -c %u:%g "$PARENT")" = "$(id -u):$(id -g)"
    test ! -e "$PROBE/$RESULT"
    RUN_TIMEOUT="${DQK_CONTEXT_TIMEOUT:-120s}"
    if [[ "$STATE" = cold && -z "${DQK_CONTEXT_TIMEOUT:-}" ]];then RUN_TIMEOUT=240s;fi
    [[ "$RUN_TIMEOUT" = 120s || "$RUN_TIMEOUT" = 240s || "$RUN_TIMEOUT" = 300s || "$RUN_TIMEOUT" = 600s ]]
    timeout "$RUN_TIMEOUT" docker run --rm --init --network none --user "$(id -u):$(id -g)" \
      --memory 1g --cpus 1 --pids-limit 64 --label project=dark-queen-of-krynn-cht \
      "${boot_args[@]}" \
      -e "DQK_CONTEXT_VIDEO=${DQK_CONTEXT_VIDEO:-0}" \
      -e "DQK_CONTEXT_ALL_MENUS=${DQK_CONTEXT_ALL_MENUS:-0}" \
      -v "$PROBE:/probe:ro" -v "$PARENT:/out" -v "$ORIG:/orig:ro" \
      --entrypoint /probe/ui-context-probe "$GO_IMAGE" \
      "$STATE_ARG" "/probe/$REQUEST" "/out/$(basename "$RESULT")" "$MODE" "${seed_args[@]}"
    ;;
  check)
    OBS="${2:?需指定觀測組相對路徑}"
    CONTROL="${3:?需指定控制組相對路徑}"
    RESULT="${4:?需指定全新比較 JSON 相對路徑}"
    ROLE="${5:-none}"
    relative "$OBS"; relative "$CONTROL"; relative "$RESULT"
    [[ "$ROLE" = none || "$ROLE" = inventory || "$ROLE" = grimoire || "$ROLE" = service ]]
    test -d "$PROBE/$OBS"
    test -d "$PROBE/$CONTROL"
    PARENT="$(dirname "$PROBE/$RESULT")"
    test -d "$PARENT"
    test "$(stat -c %u:%g "$PARENT")" = "$(id -u):$(id -g)"
    test ! -e "$PROBE/$RESULT"
    timeout 30s docker run --rm --init --network none --user "$(id -u):$(id -g)" \
      --memory 512m --cpus 1 --pids-limit 64 --label project=dark-queen-of-krynn-cht \
      -v "$PROBE:/probe:ro" -v "$ROOT/tools:/tools:ro" -v "$PARENT:/out" \
      --entrypoint python3 "$PIL_IMAGE" /tools/ui_context_check.py \
      "/probe/$OBS" "/probe/$CONTROL" "/out/$(basename "$RESULT")" --role "$ROLE"
    ;;
  preview)
    OBS="${2:?需指定已驗觀測組相對路徑}"
    COMPARISON="${3:?需指定已驗比較 JSON 相對路徑}"
    RESULT="${4:?需指定全新預覽相對路徑}"
    relative "$OBS"; relative "$COMPARISON"; relative "$RESULT"
    FONT=/home/anr2/cht/golden_box/death_knight_of_krynn/font
    TEXT="$ROOT/workplace/translation"
    test -f "$FONT/jf-openhuninn-2.1.ttf"
    test -f "$TEXT/glossary.tsv"
    test -f "$PROBE/$COMPARISON"
    test -d "$PROBE/$OBS"
    PARENT="$(dirname "$PROBE/$RESULT")"
    test -d "$PARENT"
    test "$(stat -c %u:%g "$PARENT")" = "$(id -u):$(id -g)"
    test ! -e "$PROBE/$RESULT"
    timeout 30s docker run --rm --init --network none --user "$(id -u):$(id -g)" \
      --memory 512m --cpus 1 --pids-limit 64 --label project=dark-queen-of-krynn-cht \
      -v "$PROBE:/probe:ro" -v "$ROOT/tools:/tools:ro" -v "$PARENT:/out" \
      -v "$FONT:/font:ro" -v "$TEXT:/text:ro" \
      --entrypoint python3 "$PIL_IMAGE" /tools/ui_context_preview.py \
      "/probe/$OBS" "/probe/$COMPARISON" /text/glossary.tsv /font/jf-openhuninn-2.1.ttf "/out/$(basename "$RESULT")"
    ;;
  *) printf '%s\n' '用法：ui-context.sh build | run STATE REQUEST RESULT observe|control | check OBS CONTROL RESULT [inventory|grimoire|none|service] | preview OBS COMPARISON RESULT' >&2; exit 2 ;;
esac
