#!/usr/bin/env bash
# DRAFT 原型。主機只做路徑檢查與 Docker 呼叫，不是正式遊戲啟動器。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE="$ROOT/workplace/dosgolem"
OUT="$ROOT/workplace/probe"
ORIG="$ROOT/workplace/input/dos/drkqueen"
MODULES="${DQK_GOMODCACHE:-/home/anr2/cht/dosgolem/workplace/gomodcache}"
FONT="${DQK_FONT_DIR:-/home/anr2/cht/golden_box/death_knight_of_krynn/font}"
test -d "$OUT"
test -f "$ORIG/DQK.EXE"
test -f "$OUT/startup/239m.state"
test "$(stat -c %u "$OUT")" = "$(id -u)"
test "$(stat -c %g "$OUT")" = "$(id -g)"
case "${1:-}" in
  build)
    test -f "$SOURCE/go.mod"
    test -d "$MODULES"
    test -f "$FONT/jf-openhuninn-2.1.ttf"
    test -f "$OUT/early-observe/zh-TW.tsv"
    for TARGET in "$OUT/early-live" "$OUT/early-observe" "$OUT/early-observe/glyphs-20.json"; do
      if test -e "$TARGET"; then
        test "$(stat -c %u "$TARGET")" = "$(id -u)"
        test "$(stat -c %g "$TARGET")" = "$(id -g)"
      fi
    done
    test "$(git -C "$SOURCE" rev-parse HEAD)" = f79eab6db8c64a524a06535e53e5d32b0bbcf7c8
    git -C "$SOURCE" diff --exit-code HEAD -- .
    timeout 100s docker run --rm --init --label project=dark-queen-of-krynn-cht \
      --network none --memory 3g --cpus 2 --pids-limit 128 --user "$(id -u):$(id -g)" \
      -v "$SOURCE:/src:ro" -v "$MODULES:/gomodcache:ro" -v "$ROOT/tools:/tools:ro" \
      -v "$OUT:/out" -e HOME=/tmp -e GOCACHE=/out/gocache -e GOMODCACHE=/gomodcache \
      -e GOPROXY=off -e GOMAXPROCS=2 -w /src dosgolem-go-ebiten:1.24-r1 \
      bash -c 'set -e; printf "%s\n" "{\"Replace\":{\"/src/oracle/dqk_video_observer.go\":\"/tools/oracle_video_observer.go\",\"/src/oracle/dqk_input_modifier.go\":\"/tools/oracle_input_modifier.go\"}}" >/tmp/list-overlay.json; go build -overlay /tmp/list-overlay.json -o /out/early-live /tools/early_text_live.go /tools/ui_cold_prompts.go /tools/ui_list_live.go /tools/ui_list_paragraphs.go /tools/ui_journal_reader.go /tools/ui_journal_illustrations.go /tools/ui_menu_source.go /tools/ui_hud_integer.go /tools/ui_inventory_ammo.go /tools/ui_passage_source.go /tools/ui_passage_live.go /tools/ui_original_prefix.go'
    timeout 30s docker run --rm --label project=dark-queen-of-krynn-cht \
      --network none --memory 512m --cpus 1 --pids-limit 64 --user "$(id -u):$(id -g)" \
      -v "$FONT:/font:ro" -v "$ROOT/tools:/tools:ro" -v "$OUT:/out" \
      sc-cht-hdtools:pillow11.3.0-r1 python3 /tools/menu_glyphs.py \
      /font/jf-openhuninn-2.1.ttf /out/early-observe/zh-TW.tsv /out/early-observe/glyphs-20.json
    ;;
  zh|en|fine|lifecycle-zh|lifecycle-en|lifecycle-fine)
    test -f "$OUT/early-live"
    test -f "$OUT/early-observe/glyphs-20.json"
    TRANSLATE=false
    FINE=false
    LIFECYCLE=false
    case "$1" in en|lifecycle-en) ;; *) TRANSLATE=true ;; esac
    case "$1" in fine|lifecycle-fine) FINE=true ;; esac
    case "$1" in lifecycle-*) LIFECYCLE=true ;; esac
    RUN_NAME="${2:-live-$1}"
    case "$RUN_NAME" in ''|*[!A-Za-z0-9_-]*) echo '輸出名稱只接受英數字、底線與連字號' >&2; exit 2 ;; esac
    test ! -e "$OUT/$RUN_NAME"
    timeout 120s docker run --rm --init --label project=dark-queen-of-krynn-cht \
      --network none --memory 1g --cpus 2 --pids-limit 128 --user "$(id -u):$(id -g)" \
      -v "$ORIG:/orig:ro" -v "$OUT:/out" -e DQK_LANG="$1" -e DQK_TRANSLATE="$TRANSLATE" -e DQK_FINE="$FINE" \
      -e DQK_LIFECYCLE="$LIFECYCLE" \
      -e DQK_RUN="$RUN_NAME" \
      -e GOMEMLIMIT=384MiB \
      dosgolem-go-ebiten:1.24-r1 bash -c '
        set -e
        Xvfb :99 -screen 0 800x600x24 -nolisten tcp > "/out/${DQK_RUN}-xvfb.log" 2>&1 &
        xvfb_pid=$!
        trap "kill $xvfb_pid 2>/dev/null || true; wait $xvfb_pid 2>/dev/null || true" EXIT
        for attempt in {1..50}; do test -S /tmp/.X11-unix/X99 && break; sleep 0.1; done
        export DISPLAY=:99 LIBGL_ALWAYS_SOFTWARE=1 HOME=/tmp
        set +e
        /out/early-live -state /out/startup/239m.state -out "/out/${DQK_RUN}" \
          -catalog /out/early-observe/zh-TW.tsv -glyphs /out/early-observe/glyphs-20.json \
          -translate="$DQK_TRANSLATE" -fine="$DQK_FINE" -lifecycle="$DQK_LIFECYCLE"
        result=$?
        cat /sys/fs/cgroup/memory.events > "/out/${DQK_RUN}/memory-events.txt"
        exit "$result"'
    ;;
  *) echo '用法：bash tools/early-live.sh build|zh|en|fine|lifecycle-zh|lifecycle-en|lifecycle-fine' >&2; exit 2 ;;
esac
