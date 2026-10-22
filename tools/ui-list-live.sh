#!/usr/bin/env bash
# DRAFT：已知正常快照的列表原型，不是正式啟動器。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROBE="$ROOT/workplace/probe"
ORIG="$ROOT/workplace/input/dos/drkqueen"
GO_IMAGE=sha256:8ed6bdee2bce1f32f804e888f942b25bbf62f2165a43344bb4587f3371de0581
PIL_IMAGE=sha256:44d0742ca1061bcd453440cdce925afa31c5324e115fca1334da0e364f0e2c48
FONT=/home/anr2/cht/golden_box/death_knight_of_krynn/font
relative() { [[ "$1" =~ ^[a-z0-9][a-z0-9/.-]*$ && "$1" != *..* ]]; }
test -d "$PROBE"
test "$(stat -c %u:%g "$PROBE")" = "$(id -u):$(id -g)"
case "${1:-}" in
  prepare)
    INPUT="${2:?需指定全新輸入目錄}"
    relative "$INPUT"
    test ! -e "$PROBE/$INPUT"
    test -d "$(dirname "$PROBE/$INPUT")"
    test -d "$ROOT/workplace/translation"
    test -d "$PROBE/pane-render-20261022"
    test -f "$FONT/jf-openhuninn-2.1.ttf"
    timeout 30s docker run --rm --network none --user "$(id -u):$(id -g)" --memory 512m --cpus 1 --pids-limit 64 \
      -v "$ROOT/tools:/tools:ro" -v "$ROOT/workplace/translation:/text:ro" -v "$PROBE:/probe" -v "$FONT:/font:ro" \
      --entrypoint bash "$PIL_IMAGE" -c \
      'set -e; python3 /tools/ui_list_inputs.py /text /probe/pane-render-20261022 "/probe/$1"; python3 /tools/menu_glyphs.py /font/jf-openhuninn-2.1.ttf "/probe/$1/zh-TW.tsv" "/probe/$1/glyphs-16.json" 16' -- "$INPUT"
    ;;
  build)
    test -d "$ROOT/workplace/dosgolem"
    test -d /home/anr2/cht/dosgolem/workplace/gomodcache
    test -d "$PROBE/gocache"
    test "$(git -C "$ROOT/workplace/dosgolem" rev-parse HEAD)" = f79eab6db8c64a524a06535e53e5d32b0bbcf7c8
    git -C "$ROOT/workplace/dosgolem" diff --exit-code HEAD -- .
    timeout 120s docker run --rm --init --network none --user "$(id -u):$(id -g)" --memory 2g --cpus 2 --pids-limit 128 \
      --label project=dark-queen-of-krynn-cht -e HOME=/tmp -e GOCACHE=/gocache -e GOMODCACHE=/modules -e GOPROXY=off -e GOMAXPROCS=2 \
      -v "$ROOT/workplace/dosgolem:/src:ro" -v "$ROOT/tools:/tools:ro" -v /home/anr2/cht/dosgolem/workplace/gomodcache:/modules:ro \
      -v "$PROBE/gocache:/gocache" -v "$PROBE:/out" -w /src --entrypoint bash "$GO_IMAGE" \
      -c 'set -e; test ! -e /out/ui-list-live || test "$(stat -c %u:%g /out/ui-list-live)" = "$(id -u):$(id -g)"; printf "%s\n" "{\"Replace\":{\"/src/oracle/dqk_video_observer.go\":\"/tools/oracle_video_observer.go\"}}" >/tmp/list-overlay.json; go build -overlay /tmp/list-overlay.json -o /out/ui-list-live /tools/early_text_live.go /tools/ui_list_live.go /tools/ui_menu_source.go'
    ;;
  en|zh)
    STATE="${2:?快照}"; REQUEST="${3:?一般按鍵請求}"; INPUT="${4:?輸入目錄}"; RESULT="${5:?全新輸出}"; FINE="${6:-false}"
    relative "$STATE"; relative "$REQUEST"; relative "$INPUT"; relative "$RESULT"
    [[ "$FINE" = true || "$FINE" = false ]]
    test -f "$PROBE/$STATE"; test -f "$PROBE/$REQUEST"; test -f "$PROBE/$INPUT/inputs.json"
    test -f "$PROBE/ui-list-live"; test -f "$ORIG/DQK.EXE"
    test ! -e "$PROBE/$RESULT"
    PARENT="$(dirname "$PROBE/$RESULT")"; test -d "$PARENT"
    test "$(stat -c %u:%g "$PARENT")" = "$(id -u):$(id -g)"
    TRANSLATE=false; [[ "$1" = en ]] || TRANSLATE=true
    timeout --kill-after=10s 1800s docker run --rm --init --network none --user "$(id -u):$(id -g)" --memory 3g --cpus 2 --pids-limit 128 \
      --label project=dark-queen-of-krynn-cht -e GOMAXPROCS=2 -e GOMEMLIMIT=1GiB -e LIST_STATE="$STATE" -e LIST_REQUEST="$REQUEST" \
      -e LIST_INPUT="$INPUT" -e LIST_RESULT="$(basename "$RESULT")" -e LIST_TRANSLATE="$TRANSLATE" -e LIST_FINE="$FINE" \
      -v "$PROBE:/probe:ro" -v "$PARENT:/out" -v "$ORIG:/orig:ro" --entrypoint bash "$GO_IMAGE" -c '
        set -e
        Xvfb :99 -screen 0 800x600x24 -nolisten tcp >/tmp/xvfb.log 2>&1 & xvfb_pid=$!
        trap "kill $xvfb_pid 2>/dev/null; wait $xvfb_pid 2>/dev/null" EXIT
        for attempt in {1..50}; do test -S /tmp/.X11-unix/X99 && break; sleep 0.1; done
        export DISPLAY=:99 LIBGL_ALWAYS_SOFTWARE=1
        result_status=0
        /probe/ui-list-live -list -state "/probe/$LIST_STATE" -list-request "/probe/$LIST_REQUEST" \
          -list-inputs "/probe/$LIST_INPUT/inputs.json" -source-catalog "/probe/$LIST_INPUT/en.tsv" \
          -catalog "/probe/$LIST_INPUT/zh-TW.tsv" -glyphs "/probe/$LIST_INPUT/glyphs-16.json" \
          -out "/out/$LIST_RESULT" -translate="$LIST_TRANSLATE" -fine="$LIST_FINE" || result_status=$?
        if test -d "/out/$LIST_RESULT"; then
          cat /sys/fs/cgroup/memory.peak >"/out/$LIST_RESULT/memory-peak.txt"
          cat /sys/fs/cgroup/memory.events >"/out/$LIST_RESULT/memory-events.txt"
        fi
        exit "$result_status"'
    ;;
  verify)
    EN="${2:?英文組}"; ZH="${3:?繁中組}"; INPUT="${4:?輸入}"; CONTROL="${5:?無觀測原版}"; OBS="${6:?原版觀測}"; RESULT="${7:?全新收據}"
    for PATH_ARG in "$EN" "$ZH" "$INPUT" "$CONTROL" "$OBS" "$RESULT"; do relative "$PATH_ARG"; done
    for DIR_ARG in "$EN" "$ZH" "$INPUT" "$CONTROL" "$OBS"; do test -d "$PROBE/$DIR_ARG"; done
    test ! -e "$PROBE/$RESULT"
    PARENT="$(dirname "$PROBE/$RESULT")"; test -d "$PARENT"
    test "$(stat -c %u:%g "$PARENT")" = "$(id -u):$(id -g)"
    timeout 180s docker run --rm --init --network none --user "$(id -u):$(id -g)" --memory 3g --cpus 1 --pids-limit 64 \
      --label project=dark-queen-of-krynn-cht -v "$PROBE:/probe:ro" -v "$ROOT/tools:/tools:ro" -v "$PARENT:/out" \
      --entrypoint python3 "$PIL_IMAGE" /tools/ui_list_live_check.py \
      "/probe/$EN" "/probe/$ZH" "/probe/$INPUT" "/probe/$CONTROL" "/probe/$OBS" "/out/$(basename "$RESULT")"
    ;;
  *) printf '%s\n' '用法：ui-list-live.sh prepare INPUT | build | en|zh STATE REQUEST INPUT RESULT [true|false] | verify EN ZH INPUT CONTROL OBS RESULT' >&2; exit 2 ;;
esac
